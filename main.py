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


def main():
    parser = argparse.ArgumentParser(description='NotebookLM用 Webサイト一括テキスト抽出ツール')
    parser.add_argument('url', help='スクレイピング対象のWebサイトURL')
    parser.add_argument('--max-pages', type=int, default=1000, help='最大取得ページ数（デフォルト: 1000）')
    parser.add_argument('--delay', type=float, default=1.0, help='リクエスト間隔（秒、デフォルト: 1.0）')
    parser.add_argument('--base-path', type=str, default=None, help='ベースパス（例: /run/docs/）指定しない場合は自動判定')
    parser.add_argument('--no-limit', action='store_true', help='ページ数制限を無効にする（注意: 大量のページがある場合は時間がかかります）')
    parser.add_argument('--pages-per-file', type=int, default=80, help='1ファイルあたりのページ数（デフォルト: 80）NotebookLMの制限に応じて調整')
    parser.add_argument('--javascript', action='store_true', help='JavaScript実行モードを有効にする（動的コンテンツ対応、処理時間が長くなります）')
    
    args = parser.parse_args()
    
    # --no-limitが指定された場合は無制限に
    max_pages = None if args.no_limit else args.max_pages
    
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
