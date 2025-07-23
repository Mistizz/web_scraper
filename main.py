#!/usr/bin/env python3
"""
NotebookLM用 Webサイト一括テキスト抽出ツール
指定されたWebサイトの全ページからテキストを抽出し、1つのファイルにまとめます。
JavaScript動的コンテンツにも対応。
"""

import argparse
import requests
import time
import re
import csv
import os
from urllib.parse import urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup
from typing import Set, List
from datetime import datetime
import logging

# Selenium関連のインポート
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_urls_from_file(file_path: str) -> List[str]:
    """
    ファイルからURLリストを読み込む
    
    Args:
        file_path: URLリストファイルのパス（.txt または .csv）
        
    Returns:
        List[str]: URLのリスト
    """
    urls = []
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"指定されたファイルが見つかりません: {file_path}")
    
    file_extension = os.path.splitext(file_path)[1].lower()
    
    try:
        if file_extension == '.txt':
            # txtファイルの場合：1行1URL
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line and not line.startswith('#'):  # 空行とコメント行を除外
                        if line.startswith('http://') or line.startswith('https://'):
                            urls.append(line)
                        else:
                            logger.warning(f"無効なURL（行{line_num}）: {line}")
        
        elif file_extension == '.csv':
            # csvファイルの場合：1列目がURL、またはヘッダーで'url'列を指定
            with open(file_path, 'r', encoding='utf-8') as f:
                # 最初の行を確認してヘッダーかどうか判定
                first_line = f.readline().strip()
                f.seek(0)  # ファイルの先頭に戻る
                
                reader = csv.reader(f)
                headers = next(reader)  # 最初の行を読む
                
                # 'url'列が存在するかチェック
                url_column_index = 0  # デフォルトは1列目
                if 'url' in [h.lower() for h in headers]:
                    url_column_index = [h.lower() for h in headers].index('url')
                elif not (first_line.startswith('http://') or first_line.startswith('https://')):
                    # 最初の行がURLでない場合はヘッダー行として扱う
                    pass  # url_column_indexは0のまま
                else:
                    # 最初の行がURLの場合は、それも処理対象に含める
                    f.seek(0)
                    reader = csv.reader(f)
                
                for row_num, row in enumerate(reader, 1):
                    if row and len(row) > url_column_index:
                        url = row[url_column_index].strip()
                        if url and (url.startswith('http://') or url.startswith('https://')):
                            urls.append(url)
                        elif url:
                            logger.warning(f"無効なURL（行{row_num}）: {url}")
        
        else:
            raise ValueError(f"サポートされていないファイル形式: {file_extension}")
    
    except Exception as e:
        logger.error(f"URLリストファイルの読み込みエラー: {e}")
        raise
    
    if not urls:
        raise ValueError("有効なURLが見つかりませんでした")
    
    logger.info(f"URLリストファイルから{len(urls)}個のURLを読み込みました")
    return urls


class WebsiteScraper:
    def __init__(self, base_url: str, max_pages: int = 1000, delay: float = 1.0, 
                 base_path: str = None, pages_per_file: int = 80, use_javascript: bool = False):
        """
        Webサイトスクレイピングクラス
        
        Args:
            base_url: 開始URL
            max_pages: 最大取得ページ数（Noneの場合は無制限）
            delay: リクエスト間隔（秒）
            base_path: ベースパス（指定しない場合は自動判定）
            pages_per_file: 1ファイルあたりのページ数（分割出力用）
            use_javascript: JavaScriptを実行してコンテンツを取得するかどうか
        """
        self.base_url = base_url
        self.max_pages = max_pages
        self.delay = delay
        self.pages_per_file = pages_per_file
        self.use_javascript = use_javascript
        self.driver = None
        self.visited_urls: Set[str] = set()
        self.to_visit_urls: List[str] = [base_url]
        self.extracted_content: List[str] = []
        
        # ベースドメインとベースパスを取得
        parsed_url = urlparse(base_url)
        self.base_domain = parsed_url.netloc
        
        if base_path is not None:
            # ベースパスが明示的に指定された場合
            self.base_path = base_path
            if not self.base_path.startswith('/'):
                self.base_path = '/' + self.base_path
            if not self.base_path.endswith('/'):
                self.base_path = self.base_path + '/'
            logger.info(f"ベースパス: {self.base_path} (手動指定)")
        else:
            # ベースパスを設定（ディレクトリ部分のみ）
            # 例: /run/docs/fit-for-run → /run/docs/
            path = parsed_url.path
            if path.endswith('/'):
                self.base_path = path
            else:
                # ファイル名を除いてディレクトリ部分のみ取得
                self.base_path = '/'.join(path.split('/')[:-1]) + '/'
                if not self.base_path.startswith('/'):
                    self.base_path = '/' + self.base_path
            
            # ルートパスの場合は空文字列にする
            if self.base_path == '//':
                self.base_path = '/'
            
            logger.info(f"ベースパス: {self.base_path} (自動判定)")
        
        logger.info(f"ベースドメイン: {self.base_domain}")
        
        # セッション設定
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # JavaScript実行モードの場合はSeleniumドライバーを初期化
        if self.use_javascript:
            self._setup_driver()
    
    def _setup_driver(self):
        """Seleniumドライバーのセットアップ"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # ヘッドレスモード
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            # ChromeDriverを自動でダウンロード・管理
            service = Service(ChromeDriverManager().install())
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(30)
            
            logger.info("🌐 Seleniumドライバーを初期化しました（JavaScript対応モード）")
            
        except Exception as e:
            logger.error(f"Seleniumドライバーの初期化に失敗しました: {e}")
            raise
    
    def _close_driver(self):
        """Seleniumドライバーのクローズ"""
        if self.driver:
            self.driver.quit()
            logger.info("🌐 Seleniumドライバーを終了しました")
    
    def is_valid_url(self, url: str) -> bool:
        """
        有効なURLかどうかチェック
        
        Args:
            url: チェック対象URL
            
        Returns:
            bool: 有効な場合True
        """
        parsed = urlparse(url)
        
        # 同一ドメインかチェック
        if parsed.netloc != self.base_domain:
            return False
        
        # ベースパス配下かチェック
        if not parsed.path.startswith(self.base_path):
            return False
        
        # 除外ファイル拡張子
        excluded_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.doc', '.docx', '.xls', '.xlsx', '.mp4', '.mp3'}
        path_lower = parsed.path.lower()
        
        for ext in excluded_extensions:
            if path_lower.endswith(ext):
                return False
        
        # 除外パス
        excluded_paths = {'/admin/', '/api/', '/wp-admin/', '/login/', '/logout/'}
        for excluded_path in excluded_paths:
            if excluded_path in parsed.path:
                return False
        
        return True
    
    def extract_links(self, html_content: str, current_url: str) -> List[str]:
        """
        HTMLからリンクを抽出
        
        Args:
            html_content: HTML文字列
            current_url: 現在のページURL
            
        Returns:
            List[str]: 抽出されたリンクのリスト
        """
        soup = BeautifulSoup(html_content, 'lxml')
        links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            # 相対URLを絶対URLに変換
            absolute_url = urljoin(current_url, href)
            
            # フラグメント（#section）を除去
            parsed = urlparse(absolute_url)
            clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ''))
            
            if self.is_valid_url(clean_url) and clean_url not in self.visited_urls:
                links.append(clean_url)
        
        return links
    
    def extract_text_content(self, html_content: str, url: str) -> str:
        """
        HTMLからテキストコンテンツを抽出（従来の静的版）
        
        Args:
            html_content: HTML文字列
            url: ページURL
            
        Returns:
            str: 抽出されたテキスト
        """
        soup = BeautifulSoup(html_content, 'lxml')
        
        # 不要な要素を削除
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()
        
        # タイトルを取得
        title = soup.find('title')
        title_text = title.get_text().strip() if title else "タイトルなし"
        
        # メインコンテンツを抽出
        # main, article, div.content などの要素を優先的に探す
        main_content = None
        for selector in ['main', 'article', '.content', '.main-content', '#content', '#main']:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        # メインコンテンツが見つからない場合はbodyを使用
        if not main_content:
            main_content = soup.find('body')
        
        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
        else:
            text = soup.get_text(separator='\n', strip=True)
        
        # 連続する空行を削除
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # フォーマット
        formatted_content = f"\n{'='*50}\nURL: {url}\nタイトル: {title_text}\n{'='*50}\n\n{text}\n\n"
        
        return formatted_content
    
    def extract_text_content_js(self, url: str) -> str:
        """
        SeleniumでJavaScript実行後のテキストコンテンツを抽出
        
        Args:
            url: ページURL
            
        Returns:
            str: 抽出されたテキスト
        """
        try:
            logger.info(f"🌐 JavaScript実行中: {url}")
            self.driver.get(url)
            
            # ページの読み込み完了を待機
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # 追加の待機（動的コンテンツの読み込み完了のため）
            time.sleep(3)
            
            # ページソースを取得
            page_source = self.driver.page_source
            
            # BeautifulSoupで解析
            soup = BeautifulSoup(page_source, 'lxml')
            
            # 不要な要素を削除
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                element.decompose()
            
            # タイトルを取得
            title = soup.find('title')
            title_text = title.get_text().strip() if title else "タイトルなし"
            
            # メインコンテンツを抽出
            main_content = None
            for selector in ['main', 'article', '.content', '.main-content', '#content', '#main', '[role="main"]']:
                try:
                    if selector.startswith('.') or selector.startswith('#') or selector.startswith('['):
                        main_content = soup.select_one(selector)
                    else:
                        main_content = soup.find(selector)
                    if main_content:
                        break
                except:
                    continue
            
            # メインコンテンツが見つからない場合はbodyを使用
            if not main_content:
                main_content = soup.find('body')
            
            if main_content:
                text = main_content.get_text(separator='\n', strip=True)
            else:
                text = soup.get_text(separator='\n', strip=True)
            
            # 連続する空行を削除
            text = re.sub(r'\n\s*\n', '\n\n', text)
            
            # フォーマット
            formatted_content = f"\n{'='*50}\nURL: {url}\nタイトル: {title_text}\n{'='*50}\n\n{text}\n\n"
            
            return formatted_content
            
        except TimeoutException:
            logger.error(f"ページ読み込みタイムアウト: {url}")
            return f"\n{'='*50}\nURL: {url}\nエラー: ページ読み込みタイムアウト\n{'='*50}\n\n"
        except WebDriverException as e:
            logger.error(f"WebDriverエラー - {url}: {e}")
            return f"\n{'='*50}\nURL: {url}\nエラー: {e}\n{'='*50}\n\n"
    
    def scrape_page(self, url: str) -> bool:
        """
        単一ページをスクレイピング（JavaScript対応版）
        
        Args:
            url: スクレイピング対象URL
            
        Returns:
            bool: 成功した場合True
        """
        try:
            if self.use_javascript:
                # JavaScript実行モード
                content = self.extract_text_content_js(url)
                self.extracted_content.append(content)
                
                # リンク抽出もSeleniumで実行
                page_source = self.driver.page_source
                new_links = self.extract_links(page_source, url)
                for link in new_links:
                    if link not in self.visited_urls and link not in self.to_visit_urls:
                        self.to_visit_urls.append(link)
                
            else:
                # 従来の静的スクレイピング
                logger.info(f"取得中: {url}")
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                # テキストコンテンツを抽出
                content = self.extract_text_content(response.text, url)
                self.extracted_content.append(content)
                
                # 新しいリンクを収集
                new_links = self.extract_links(response.text, url)
                for link in new_links:
                    if link not in self.visited_urls and link not in self.to_visit_urls:
                        self.to_visit_urls.append(link)
            
            return True
            
        except requests.RequestException as e:
            logger.error(f"エラー - {url}: {e}")
            return False
        except Exception as e:
            logger.error(f"予期しないエラー - {url}: {e}")
            return False
    
    def discover_all_pages(self) -> List[str]:
        """
        全ページのURLを事前に探索（JavaScript対応版）
        
        Returns:
            List[str]: 発見された全ページURLのリスト
        """
        logger.info("📋 事前探索開始: 全ページURLを収集中...")
        
        discovered_urls: Set[str] = set()
        to_explore: List[str] = [self.base_url]
        explored: Set[str] = set()
        
        while to_explore:
            current_url = to_explore.pop(0)
            
            if current_url in explored:
                continue
                
            explored.add(current_url)
            discovered_urls.add(current_url)
            
            try:
                logger.info(f"探索中: {current_url}")
                
                if self.use_javascript:
                    # JavaScript実行モード
                    self.driver.get(current_url)
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    time.sleep(2)  # 動的コンテンツの読み込み待機
                    page_source = self.driver.page_source
                else:
                    # 静的スクレイピング
                    response = self.session.get(current_url, timeout=30)
                    response.raise_for_status()
                    page_source = response.text
                
                # 新しいリンクを収集
                new_links = self.extract_links(page_source, current_url)
                for link in new_links:
                    if link not in discovered_urls and link not in to_explore:
                        to_explore.append(link)
                
                # 進捗表示（10の倍数で表示）
                if len(discovered_urls) % 10 == 0:
                    logger.info(f"📊 発見ページ数: {len(discovered_urls)}ページ")
                
            except Exception as e:
                logger.warning(f"探索エラー - {current_url}: {e}")
                continue
            
            # 探索間隔（スクレイピングより短めに）
            time.sleep(self.delay * 0.5)
        
        sorted_urls = sorted(list(discovered_urls))
        logger.info(f"📋 事前探索完了: 総ページ数 {len(sorted_urls)}ページ")
        
        return sorted_urls
    
    def scrape_website(self) -> (int, int):
        """
        Webサイト全体をスクレイピング（JavaScript対応版）
        
        Returns:
            (int, int): 発見された総ページ数, 取得されたページ数
        """
        try:
            logger.info(f"スクレイピング開始: {self.base_url}")
            logger.info(f"対象範囲: {self.base_domain}{self.base_path}* 配下")
            if self.use_javascript:
                logger.info("💻 JavaScript実行モード: 動的コンテンツにも対応")
            
            # 事前探索で全ページを発見
            all_pages = self.discover_all_pages()
            total_pages = len(all_pages)
            
            print(f"\n🔍 事前探索結果:")
            print(f"📊 発見された総ページ数: {total_pages}ページ")
            
            if self.max_pages is None:
                pages_to_process = total_pages
                print(f"📥 処理予定ページ数: {pages_to_process}ページ (制限なし)")
            else:
                pages_to_process = min(total_pages, self.max_pages)
                print(f"📥 処理予定ページ数: {pages_to_process}ページ (制限: {self.max_pages})")
                if total_pages > self.max_pages:
                    print(f"⚠️  注意: {total_pages - self.max_pages}ページが制限により除外されます")
            
            print(f"⏱️  推定処理時間: 約{pages_to_process * self.delay / 60:.1f}分")
            print("-" * 60)
            
            # 実際のスクレイピング開始
            logger.info(f"📄 テキスト抽出開始...")
            
            # 処理するページのリストを設定
            self.to_visit_urls = all_pages[:pages_to_process] if self.max_pages else all_pages
            self.visited_urls = set()  # リセット
            
            page_count = 0
            
            while self.to_visit_urls:
                current_url = self.to_visit_urls.pop(0)
                
                if current_url in self.visited_urls:
                    continue
                
                self.visited_urls.add(current_url)
                
                if self.scrape_page(current_url):
                    page_count += 1
                    if self.max_pages is None:
                        logger.info(f"進捗: {page_count}/{total_pages}")
                    else:
                        max_display = min(total_pages, self.max_pages)
                        logger.info(f"進捗: {page_count}/{max_display}")
                
                # リクエスト間隔
                time.sleep(self.delay)
            
            logger.info(f"スクレイピング完了: {page_count}ページ取得")
            
            # ファイル名のベースを作成
            domain_name = self.base_domain.replace('.', '_')
            path_name = self.base_path.replace('/', '_').strip('_')
            if path_name:
                filename_base = f"{domain_name}_{path_name}"
            else:
                filename_base = domain_name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"{filename_base}_all_content_{timestamp}.txt"
            
            # 分割保存を実行
            self.save_content_split(base_filename, total_pages, page_count)
            
            return total_pages, page_count
            
        finally:
            # Seleniumドライバーのクリーンアップ
            if self.use_javascript:
                self._close_driver()
    
    def save_content_split(self, base_filename: str, total_pages: int, pages_processed: int):
        """
        コンテンツを複数ファイルに分割して保存
        
        Args:
            base_filename: ベースファイル名
            total_pages: 発見された総ページ数
            pages_processed: 実際に処理されたページ数
        """
        if not self.extracted_content:
            logger.warning("保存するコンテンツがありません")
            return
        
        # 分割数を計算
        total_files = (len(self.extracted_content) + self.pages_per_file - 1) // self.pages_per_file
        
        logger.info(f"📂 分割保存開始: {total_files}個のファイルに分割します")
        print(f"\n📂 分割保存中...")
        print(f"🗂️  ファイル分割: {self.pages_per_file}ページずつ、計{total_files}ファイル")
        
        # ベースファイル名から拡張子を分離
        base_name = base_filename.replace('.txt', '')
        
        saved_files = []
        
        for file_index in range(total_files):
            start_idx = file_index * self.pages_per_file
            end_idx = min(start_idx + self.pages_per_file, len(self.extracted_content))
            
            # このファイルのコンテンツ
            file_content = self.extracted_content[start_idx:end_idx]
            pages_in_file = len(file_content)
            
            # ファイル名を生成
            filename = f"{base_name}_part{file_index + 1}_of_{total_files}.txt"
            
            # ヘッダーを作成
            domain_name = self.base_domain
            header = f"""NotebookLM用 全サイトコンテンツ (パート {file_index + 1}/{total_files})
サイト: {domain_name}
対象パス: {self.base_path}* 配下
抽出日時: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
発見ページ数: {total_pages}ページ
取得ページ数: {pages_processed}ページ
このファイル: {pages_in_file}ページ (ページ{start_idx + 1}〜{end_idx})

{'='*80}

"""
            
            # ファイル内容を結合
            full_content = header + "\n".join(file_content)
            
            # ファイル保存
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(full_content)
                
                file_size_kb = len(full_content.encode('utf-8')) / 1024
                logger.info(f"ファイル保存完了: {filename} ({file_size_kb:.1f} KB)")
                saved_files.append(filename)
                
            except Exception as e:
                logger.error(f"ファイル保存エラー - {filename}: {e}")
        
        # 保存結果の表示
        print(f"\n✅ 分割保存完了!")
        print(f"📁 保存ファイル数: {len(saved_files)}個")
        for i, filename in enumerate(saved_files, 1):
            file_size_kb = len(open(filename, 'r', encoding='utf-8').read().encode('utf-8')) / 1024
            print(f"   {i}. {filename} ({file_size_kb:.1f} KB)")
        
        print(f"\n💡 NotebookLMでの使用方法:")
        print(f"   各ファイルを個別にアップロードしてください")
        print(f"   パート1から順番にアップロードすることをおすすめします")
    
    def save_content(self, content: str, filename: str):
        """
        コンテンツをファイルに保存（従来の単一ファイル保存）
        
        Args:
            content: 保存するコンテンツ
            filename: ファイル名
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"ファイル保存完了: {filename}")
            print(f"\n✅ コンテンツを保存しました: {filename}")
            print(f"📄 ファイルサイズ: {len(content.encode('utf-8')) / 1024:.1f} KB")
        except Exception as e:
            logger.error(f"ファイル保存エラー: {e}")
            print(f"❌ ファイル保存に失敗しました: {e}")


def process_multiple_urls(url_list: List[str], max_pages: int = None, delay: float = 1.0, 
                         base_path: str = None, pages_per_file: int = 80, use_javascript: bool = False, 
                         exact_urls: bool = False):
    """
    複数URLを順次処理してコンテンツを統合
    
    Args:
        url_list: 処理対象URLのリスト
        max_pages: 1サイトあたりの最大取得ページ数（exact_urlsがTrueの場合は無視）
        delay: リクエスト間隔
        base_path: ベースパス（exact_urlsがTrueの場合は無視）
        pages_per_file: 1ファイルあたりのページ数
        use_javascript: JavaScript実行モード
        exact_urls: Trueの場合、指定されたURLのみを処理（リンク追跡なし）
        
    Returns:
        (int, int): 総発見ページ数、総取得ページ数
    """
    all_content = []
    total_discovered = 0
    total_processed = 0
    
    if exact_urls:
        print(f"\n🎯 指定URL限定処理開始: {len(url_list)}ページを個別処理")
        print("📌 各URLのページのみ取得（下位ページの自動収集は行いません）")
    else:
        print(f"\n🔗 複数URL処理開始: {len(url_list)}サイトを順次処理")
        print("🌐 各URLを起点として下位ページも自動収集します")
    print("-" * 60)
    
    for i, url in enumerate(url_list, 1):
        print(f"\n📍 [{i}/{len(url_list)}] 処理中: {url}")
        print("-" * 40)
        
        try:
            if exact_urls:
                # 指定URLのみ処理モード
                content = scrape_single_url(url, use_javascript, delay)
                if content:
                    all_content.append(content)
                    total_processed += 1
                    total_discovered += 1
                    print(f"✅ [{i}/{len(url_list)}] 完了: 1ページ取得")
                else:
                    print(f"❌ [{i}/{len(url_list)}] 失敗: コンテンツ取得できませんでした")
            else:
                # 従来の下位ページ自動収集モード
                scraper = WebsiteScraper(url, max_pages, delay, base_path, pages_per_file, use_javascript)
                discovered, processed = scraper.scrape_website()
                
                # コンテンツを統合
                all_content.extend(scraper.extracted_content)
                total_discovered += discovered
                total_processed += processed
                
                print(f"✅ [{i}/{len(url_list)}] 完了: {processed}ページ取得")
            
            # サイト間の間隔
            if i < len(url_list):
                time.sleep(delay * 2)  # サイト間は通常の2倍の間隔
                
        except Exception as e:
            logger.error(f"エラー - {url}: {e}")
            print(f"❌ [{i}/{len(url_list)}] スキップ: {url} - {e}")
            continue
    
    # 統合ファイルを保存
    if all_content:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if exact_urls:
            base_filename = f"exact_urls_content_{timestamp}.txt"
        else:
            base_filename = f"multi_site_content_{timestamp}.txt"
        save_content_split_unified(all_content, base_filename, total_discovered, total_processed, pages_per_file)
    
    return total_discovered, total_processed


def scrape_single_url(url: str, use_javascript: bool = False, delay: float = 1.0) -> str:
    """
    単一URLのコンテンツのみを取得（リンク追跡なし）
    
    Args:
        url: 取得対象URL
        use_javascript: JavaScript実行モード
        delay: 遅延時間（JavaScript実行時の待機に使用）
        
    Returns:
        str: 抽出されたコンテンツ（取得失敗時はNone）
    """
    try:
        if use_javascript:
            # JavaScript実行モード
            logger.info(f"🌐 JavaScript実行中: {url}")
            
            # 簡易的なSeleniumドライバーセットアップ
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(30)
            
            try:
                driver.get(url)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(3)  # 動的コンテンツの読み込み完了待機
                
                page_source = driver.page_source
                
                # BeautifulSoupで解析
                soup = BeautifulSoup(page_source, 'lxml')
                
                # 不要な要素を削除
                for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                    element.decompose()
                
                # タイトルを取得
                title = soup.find('title')
                title_text = title.get_text().strip() if title else "タイトルなし"
                
                # メインコンテンツを抽出
                main_content = None
                for selector in ['main', 'article', '.content', '.main-content', '#content', '#main', '[role="main"]']:
                    try:
                        if selector.startswith('.') or selector.startswith('#') or selector.startswith('['):
                            main_content = soup.select_one(selector)
                        else:
                            main_content = soup.find(selector)
                        if main_content:
                            break
                    except:
                        continue
                
                if not main_content:
                    main_content = soup.find('body')
                
                if main_content:
                    text = main_content.get_text(separator='\n', strip=True)
                else:
                    text = soup.get_text(separator='\n', strip=True)
                
                # 連続する空行を削除
                text = re.sub(r'\n\s*\n', '\n\n', text)
                
                # フォーマット
                formatted_content = f"\n{'='*50}\nURL: {url}\nタイトル: {title_text}\n{'='*50}\n\n{text}\n\n"
                
                return formatted_content
                
            finally:
                driver.quit()
                
        else:
            # 静的スクレイピング
            logger.info(f"取得中: {url}")
            
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            
            response = session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 不要な要素を削除
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                element.decompose()
            
            # タイトルを取得
            title = soup.find('title')
            title_text = title.get_text().strip() if title else "タイトルなし"
            
            # メインコンテンツを抽出
            main_content = None
            for selector in ['main', 'article', '.content', '.main-content', '#content', '#main']:
                main_content = soup.select_one(selector)
                if main_content:
                    break
            
            if not main_content:
                main_content = soup.find('body')
            
            if main_content:
                text = main_content.get_text(separator='\n', strip=True)
            else:
                text = soup.get_text(separator='\n', strip=True)
            
            # 連続する空行を削除
            text = re.sub(r'\n\s*\n', '\n\n', text)
            
            # フォーマット
            formatted_content = f"\n{'='*50}\nURL: {url}\nタイトル: {title_text}\n{'='*50}\n\n{text}\n\n"
            
            return formatted_content
            
    except Exception as e:
        logger.error(f"単一URL取得エラー - {url}: {e}")
        return None


def save_content_split_unified(content_list: List[str], base_filename: str, 
                              total_discovered: int, total_processed: int, pages_per_file: int):
    """
    統合コンテンツを複数ファイルに分割して保存
    
    Args:
        content_list: 全コンテンツのリスト
        base_filename: ベースファイル名
        total_discovered: 総発見ページ数
        total_processed: 総処理ページ数
        pages_per_file: 1ファイルあたりのページ数
    """
    if not content_list:
        logger.warning("保存するコンテンツがありません")
        return
    
    # 分割数を計算
    total_files = (len(content_list) + pages_per_file - 1) // pages_per_file
    
    logger.info(f"📂 統合ファイル保存開始: {total_files}個のファイルに分割します")
    print(f"\n📂 統合ファイル保存中...")
    print(f"🗂️  ファイル分割: {pages_per_file}ページずつ、計{total_files}ファイル")
    
    # ベースファイル名から拡張子を分離
    base_name = base_filename.replace('.txt', '')
    
    saved_files = []
    
    for file_index in range(total_files):
        start_idx = file_index * pages_per_file
        end_idx = min(start_idx + pages_per_file, len(content_list))
        
        # このファイルのコンテンツ
        file_content = content_list[start_idx:end_idx]
        pages_in_file = len(file_content)
        
        # ファイル名を生成
        filename = f"{base_name}_part{file_index + 1}_of_{total_files}.txt"
        
        # ヘッダーを作成
        header = f"""NotebookLM用 複数サイト統合コンテンツ (パート {file_index + 1}/{total_files})
抽出日時: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
総発見ページ数: {total_discovered}ページ
総取得ページ数: {total_processed}ページ
このファイル: {pages_in_file}ページ (ページ{start_idx + 1}〜{end_idx})

{'='*80}

"""
        
        # ファイル内容を結合
        full_content = header + "\n".join(file_content)
        
        # ファイル保存
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            file_size_kb = len(full_content.encode('utf-8')) / 1024
            logger.info(f"ファイル保存完了: {filename} ({file_size_kb:.1f} KB)")
            saved_files.append(filename)
            
        except Exception as e:
            logger.error(f"ファイル保存エラー - {filename}: {e}")
    
    # 保存結果の表示
    print(f"\n✅ 統合ファイル保存完了!")
    print(f"📁 保存ファイル数: {len(saved_files)}個")
    for i, filename in enumerate(saved_files, 1):
        file_size_kb = len(open(filename, 'r', encoding='utf-8').read().encode('utf-8')) / 1024
        print(f"   {i}. {filename} ({file_size_kb:.1f} KB)")
    
    print(f"\n💡 NotebookLMでの使用方法:")
    print(f"   各ファイルを個別にアップロードしてください")
    print(f"   パート1から順番にアップロードすることをおすすめします")


def extract_page_metadata(url: str, use_javascript: bool = False) -> dict:
    """
    単一ページのメタデータ（URL、title、h1）を抽出
    
    Args:
        url: 取得対象URL
        use_javascript: JavaScript実行モード
        
    Returns:
        dict: {'url': str, 'title': str, 'h1': str, 'status': str}
    """
    try:
        if use_javascript:
            # JavaScript実行モード
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(30)
            
            try:
                driver.get(url)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(2)  # 動的コンテンツの読み込み完了待機
                
                page_source = driver.page_source
                soup = BeautifulSoup(page_source, 'lxml')
                
            finally:
                driver.quit()
        else:
            # 静的スクレイピング
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            
            response = session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
        
        # titleタグを取得
        title_tag = soup.find('title')
        title = title_tag.get_text().strip() if title_tag else ""
        
        # h1タグを取得（複数ある場合は最初のもの）
        h1_tag = soup.find('h1')
        h1 = h1_tag.get_text().strip() if h1_tag else ""
        
        return {
            'url': url,
            'title': title,
            'h1': h1,
            'status': 'success'
        }
        
    except Exception as e:
        logger.warning(f"メタデータ取得エラー - {url}: {e}")
        return {
            'url': url,
            'title': "",
            'h1': "",
            'status': f'error: {str(e)}'
        }


def generate_sitemap(base_url: str, base_path: str = None, use_javascript: bool = False, 
                    delay: float = 1.0, output_format: str = 'csv') -> str:
    """
    サイトマップ（URL、title、h1のリスト）を生成
    
    Args:
        base_url: 基準URL
        base_path: ベースパス
        use_javascript: JavaScript実行モード
        delay: リクエスト間隔
        output_format: 出力形式（'csv' または 'txt'）
        
    Returns:
        str: 生成されたファイル名
    """
    logger.info(f"📋 サイトマップ生成開始: {base_url}")
    
    # WebsiteScraperクラスを使って全URLを発見
    scraper = WebsiteScraper(base_url, max_pages=None, delay=delay, 
                           base_path=base_path, use_javascript=use_javascript)
    
    print(f"\n📋 サイトマップ生成開始")
    print(f"📍 対象URL: {base_url}")
    print(f"📁 ベースパス: {scraper.base_path}")
    if use_javascript:
        print(f"💻 JavaScript実行モード: 有効")
    else:
        print(f"🌐 静的スクレイピングモード: 標準")
    print(f"⏱️  遅延時間: {delay}秒")
    print("-" * 50)
    
    # 全ページURLを発見
    all_urls = scraper.discover_all_pages()
    
    print(f"\n📊 メタデータ抽出開始: {len(all_urls)}ページ")
    print("-" * 40)
    
    # 各URLのメタデータを取得
    metadata_list = []
    
    for i, url in enumerate(all_urls, 1):
        print(f"🔍 [{i}/{len(all_urls)}] 処理中: {url}")
        
        metadata = extract_page_metadata(url, use_javascript)
        metadata_list.append(metadata)
        
        # 進捗表示
        if metadata['status'] == 'success':
            title_preview = metadata['title'][:50] + "..." if len(metadata['title']) > 50 else metadata['title']
            print(f"   ✅ Title: {title_preview}")
        else:
            print(f"   ❌ {metadata['status']}")
        
        # 遅延
        if i < len(all_urls):
            time.sleep(delay)
    
    # ファイル保存
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    domain_name = scraper.base_domain.replace('.', '_')
    path_name = scraper.base_path.replace('/', '_').strip('_')
    
    if path_name:
        filename_base = f"{domain_name}_{path_name}_sitemap_{timestamp}"
    else:
        filename_base = f"{domain_name}_sitemap_{timestamp}"
    
    if output_format.lower() == 'csv':
        filename = f"{filename_base}.csv"
        save_sitemap_csv(metadata_list, filename)
    else:
        filename = f"{filename_base}.txt"
        save_sitemap_txt(metadata_list, filename)
    
    # Seleniumドライバーのクリーンアップ
    if use_javascript and scraper.driver:
        scraper._close_driver()
    
    return filename


def save_sitemap_csv(metadata_list: list, filename: str):
    """
    サイトマップをCSV形式で保存
    
    Args:
        metadata_list: メタデータのリスト
        filename: 保存ファイル名
    """
    try:
        with open(filename, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            
            # ヘッダー行
            writer.writerow(['URL', 'Title', 'H1', 'Status'])
            
            # データ行
            for metadata in metadata_list:
                writer.writerow([
                    metadata['url'],
                    metadata['title'],
                    metadata['h1'],
                    metadata['status']
                ])
        
        success_count = sum(1 for m in metadata_list if m['status'] == 'success')
        file_size_kb = len(open(filename, 'r', encoding='utf-8').read().encode('utf-8')) / 1024
        
        print(f"\n✅ サイトマップ保存完了!")
        print(f"📁 ファイル名: {filename}")
        print(f"📄 ファイルサイズ: {file_size_kb:.1f} KB")
        print(f"📊 総URL数: {len(metadata_list)}")
        print(f"✅ 成功: {success_count}")
        print(f"❌ エラー: {len(metadata_list) - success_count}")
        
        logger.info(f"サイトマップCSV保存完了: {filename}")
        
    except Exception as e:
        logger.error(f"サイトマップCSV保存エラー: {e}")
        print(f"❌ ファイル保存に失敗しました: {e}")


def save_sitemap_txt(metadata_list: list, filename: str):
    """
    サイトマップをTXT形式で保存
    
    Args:
        metadata_list: メタデータのリスト
        filename: 保存ファイル名
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            # ヘッダー
            f.write("サイトマップ - URL・Title・H1 一覧\n")
            f.write(f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"総URL数: {len(metadata_list)}\n")
            f.write("=" * 80 + "\n\n")
            
            # データ
            for i, metadata in enumerate(metadata_list, 1):
                f.write(f"{i}. URL: {metadata['url']}\n")
                f.write(f"   Title: {metadata['title']}\n")
                f.write(f"   H1: {metadata['h1']}\n")
                f.write(f"   Status: {metadata['status']}\n")
                f.write("-" * 40 + "\n")
        
        success_count = sum(1 for m in metadata_list if m['status'] == 'success')
        file_size_kb = len(open(filename, 'r', encoding='utf-8').read().encode('utf-8')) / 1024
        
        print(f"\n✅ サイトマップ保存完了!")
        print(f"📁 ファイル名: {filename}")
        print(f"📄 ファイルサイズ: {file_size_kb:.1f} KB")
        print(f"📊 総URL数: {len(metadata_list)}")
        print(f"✅ 成功: {success_count}")
        print(f"❌ エラー: {len(metadata_list) - success_count}")
        
        logger.info(f"サイトマップTXT保存完了: {filename}")
        
    except Exception as e:
        logger.error(f"サイトマップTXT保存エラー: {e}")
        print(f"❌ ファイル保存に失敗しました: {e}")


def main():
    parser = argparse.ArgumentParser(description='NotebookLM用 Webサイト一括テキスト抽出ツール')
    parser.add_argument('url', nargs='?', help='スクレイピング対象のWebサイトURL（--url-listと排他的）')
    parser.add_argument('--url-list', type=str, help='URLリストファイル（.txt または .csv）')
    parser.add_argument('--max-pages', type=int, default=1000, help='最大取得ページ数（デフォルト: 1000）')
    parser.add_argument('--delay', type=float, default=1.0, help='リクエスト間隔（秒、デフォルト: 1.0）')
    parser.add_argument('--base-path', type=str, default=None, help='ベースパス（例: /run/docs/）指定しない場合は自動判定')
    parser.add_argument('--no-limit', action='store_true', help='ページ数制限を無効にする（注意: 大量のページがある場合は時間がかかります）')
    parser.add_argument('--pages-per-file', type=int, default=80, help='1ファイルあたりのページ数（デフォルト: 80）NotebookLMの制限に応じて調整')
    parser.add_argument('--javascript', action='store_true', help='JavaScript実行モードを有効にする（動的コンテンツ対応、処理時間が長くなります）')
    parser.add_argument('--exact-urls', action='store_true', help='指定されたURLリストのURLのみを処理し、リンク追跡を行わない')
    parser.add_argument('--generate-sitemap', action='store_true', help='サイトマップ（URL・title・h1のリスト）を生成する')
    parser.add_argument('--sitemap-format', type=str, choices=['csv', 'txt'], default='csv', help='サイトマップの出力形式（デフォルト: csv）')
    
    args = parser.parse_args()
    
    # URL または URL-list の排他的チェック
    if not args.url and not args.url_list:
        parser.error("URLまたは--url-listのいずれかを指定してください")
    
    if args.url and args.url_list:
        parser.error("URLと--url-listは同時に指定できません")
    
    # --exact-urls は --url-list と組み合わせてのみ使用可能
    if args.exact_urls and not args.url_list:
        parser.error("--exact-urlsオプションは--url-listと組み合わせてのみ使用できます")
    
    # --generate-sitemap は単一URLとのみ組み合わせ可能
    if args.generate_sitemap and args.url_list:
        parser.error("--generate-sitemapオプションは単一URLでのみ使用できます")
    
    if args.generate_sitemap and args.exact_urls:
        parser.error("--generate-sitemapと--exact-urlsは同時に使用できません")
    
    # --no-limitが指定された場合は無制限に
    max_pages = None if args.no_limit else args.max_pages
    
    if args.generate_sitemap:
        # サイトマップ生成モード
        print(f"📋 サイトマップ生成モード")
        print(f"📍 対象URL: {args.url}")
        if args.base_path:
            print(f"📁 ベースパス: {args.base_path} (手動指定)")
        else:
            print(f"📁 ベースパス: 自動判定")
        print(f"📊 出力形式: {args.sitemap_format.upper()}")
        print(f"⏱️  遅延時間: {args.delay}秒")
        if args.javascript:
            print(f"💻 JavaScript実行モード: 有効 (動的コンテンツ対応)")
        else:
            print(f"🌐 静的スクレイピングモード: 標準")
        print("-" * 50)
        
        try:
            filename = generate_sitemap(args.url, args.base_path, args.javascript, 
                                      args.delay, args.sitemap_format)
            print(f"\n🎉 サイトマップ生成完了！")
            print(f"📁 生成ファイル: {filename}")
            print(f"💡 このファイルでサイト全体の構造を確認できます")
            
        except Exception as e:
            logger.error(f"サイトマップ生成エラー: {e}")
            print(f"❌ エラー: {e}")
            return
    
    elif args.url_list:
        # URLリストファイルからの処理
        try:
            url_list = load_urls_from_file(args.url_list)
            
            print(f"🚀 複数Webサイトスクレイピング開始")
            print(f"📋 URLリストファイル: {args.url_list}")
            print(f"📊 対象サイト数: {len(url_list)}サイト")
            if args.exact_urls:
                print(f"📁 ベースパス: 無視（各URLを直接処理）")
            elif args.base_path:
                print(f"📁 ベースパス: {args.base_path} (手動指定)")
            else:
                print(f"📁 ベースパス: 各サイトで自動判定")
            if args.exact_urls:
                print(f"📊 ページ数制限: 各URL1ページのみ（--max-pages設定は無視）")
            elif args.no_limit:
                print(f"📊 1サイトあたり最大ページ数: 無制限 ⚠️")
            else:
                print(f"📊 1サイトあたり最大ページ数: {args.max_pages}")
            print(f"🗂️  分割設定: {args.pages_per_file}ページずつファイル分割")
            print(f"⏱️  遅延時間: {args.delay}秒")
            if args.javascript:
                print(f"💻 JavaScript実行モード: 有効 (動的コンテンツ対応)")
            else:
                print(f"🌐 静的スクレイピングモード: 標準")
            if args.exact_urls:
                print(f"🎯 処理モード: 指定URL限定 (各URLのページのみ処理)")
            else:
                print(f"🌐 処理モード: サイト全体収集 (各URLから下位ページも自動収集)")
            print("-" * 50)
            
            total_discovered, total_processed = process_multiple_urls(
                url_list, max_pages, args.delay, args.base_path, args.pages_per_file, args.javascript, args.exact_urls
            )
            
            if args.exact_urls:
                print("\n🎉 指定URL限定処理完了！")
                print(f"📥 処理ページ数: {total_processed}ページ")
                print(f"NotebookLMに指定された{total_processed}ページのコンテンツをアップロードしてご利用ください。")
            else:
                print("\n🎉 複数サイトスクレイピング完了！")
                print(f"📊 総発見ページ数: {total_discovered}ページ")
                print(f"📥 総取得ページ数: {total_processed}ページ")
                print(f"NotebookLMに統合された{total_processed}ページのコンテンツをアップロードしてご利用ください。")
            
        except Exception as e:
            logger.error(f"URLリスト処理エラー: {e}")
            print(f"❌ エラー: {e}")
            return
    
    else:
        # 単一URLからの処理（既存の処理）
        print(f"🚀 Webサイトスクレイピング開始")
        print(f"📍 対象URL: {args.url}")
        if args.base_path:
            print(f"📁 ベースパス: {args.base_path} (手動指定)")
        else:
            print(f"📁 ベースパス: 自動判定")
        if args.no_limit:
            print(f"📊 最大ページ数: 無制限 ⚠️")
        else:
            print(f"📊 最大ページ数: {args.max_pages}")
        print(f"🗂️  分割設定: {args.pages_per_file}ページずつファイル分割")
        print(f"⏱️  遅延時間: {args.delay}秒")
        if args.javascript:
            print(f"💻 JavaScript実行モード: 有効 (動的コンテンツ対応)")
        else:
            print(f"🌐 静的スクレイピングモード: 標準")
        print("-" * 50)
        
        scraper = WebsiteScraper(args.url, max_pages, args.delay, args.base_path, args.pages_per_file, args.javascript)
        total_pages, page_count = scraper.scrape_website()
        
        print("\n🎉 スクレイピング完了！")
        print(f"NotebookLMに {page_count}ページのコンテンツをアップロードしてご利用ください。")


if __name__ == "__main__":
    main()
