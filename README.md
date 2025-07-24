# NotebookLM用 Webサイト一括テキスト抽出ツール

指定されたWebサイトの全ページからテキストを抽出し、NotebookLMで読み込みやすい1つのテキストファイルにまとめるPythonツールです。

## 🎯 主な機能

- **単一サイト処理**: 指定されたWebサイトのドメイン内の全ページを自動収集
- **🆕 複数サイト処理**: URLリストファイル（txt/csv）から複数サイトを一括処理
- **🗺️ サイトマップ生成**: 下位ページのURL・Title・H1タグ一覧を生成（NEW!）
- **事前探索**: 処理開始前に全ページ数を把握・表示
- **パス階層での絞り込み**: 指定されたURL配下のページのみを対象
- **分割出力**: NotebookLMの制限に対応した複数ファイル出力
- **JavaScript対応**: SPA（React/Vue.js等）サイトの動的コンテンツにも対応
- HTMLタグを除去してクリーンなテキストを抽出  
- 全ページのコンテンツを1つのファイルに結合
- NotebookLMでの分析に最適化されたフォーマット

## 🌐 対応サイト

### 静的サイト（標準モード）
- 従来のHTMLサイト
- WordPressサイト
- 静的サイトジェネレーター（Jekyll、Hugo等）
- サーバーサイドレンダリング（SSR）サイト

### 動的サイト（JavaScript実行モード）
- **SPA（Single Page Application）**
- React、Vue.js、Angularアプリ
- APIドキュメントサイト（例：Chatwork API）
- 動的にコンテンツが読み込まれるサイト
- Ajax/Fetchでデータを取得するサイト

## 📦 インストール

```bash
# 依存関係をインストール
uv sync

# または pip を使用する場合
pip install requests beautifulsoup4 lxml selenium webdriver-manager
```

## 🚀 使い方

### 🔗 URLリストからの一括処理（🆕 新機能）

```bash
# txtファイルから複数サイトを処理（各URLから下位ページも自動収集）
python main.py --url-list sites.txt

# csvファイルから複数サイトを処理
python main.py --url-list sites.csv --javascript --delay 2.0

# 🎯 指定URLのみ処理（リンク追跡なし）- NEW!
python main.py --url-list specific_pages.txt --exact-urls
```

#### URLリストファイルの形式

**txtファイル（sites.txt）:**
```
https://example.com/docs/
https://another-site.com/api/
https://third-site.org/guide/
# コメント行（#で始まる行は無視されます）
https://fourth-site.com/
```

**csvファイル（sites.csv）:**
```csv
url,description
https://example.com/docs/,Example Documentation
https://another-site.com/api/,API Reference  
https://third-site.org/guide/,User Guide
```

または、ヘッダーなしの場合：
```csv
https://example.com/docs/
https://another-site.com/api/
https://third-site.org/guide/
```

### 🗺️ サイトマップ生成（🆕 NEW!）

```bash
# サイトマップをCSV形式で生成
python main.py https://example.com --generate-sitemap

# サイトマップをTXT形式で生成
python main.py https://example.com --generate-sitemap --sitemap-format txt

# JavaScript対応でサイトマップ生成（SPA向け）
python main.py https://docs.api-site.com --generate-sitemap --javascript
```

### 単一サイトの処理（従来の機能）

```bash
# 静的サイト（標準・高速）
python main.py https://example.com

# JavaScript実行が必要なSPAサイト（低速）
python main.py https://developer.chatwork.com/reference/ --javascript
```

### オプション付きで実行

```bash
# 最大50ページまで取得、2秒間隔で実行
python main.py https://example.com --max-pages 50 --delay 2.0

# URLリストで各サイト30ページまで、慎重に処理
python main.py --url-list sites.txt --max-pages 30 --delay 3.0 --javascript
```

### コマンドラインオプション

- `url` (条件付き必須): スクレイピング対象のWebサイトのURL（--url-listと排他的）
- `--url-list` (条件付き必須): URLリストファイル（.txt または .csv）
- `--max-pages`: 最大取得ページ数 (デフォルト: 1000) ※URLリスト使用時は1サイトあたり
- `--delay`: リクエスト間隔（秒） (デフォルト: 1.0)
- `--base-path`: ベースパス (例: `/run/docs/`) 指定しない場合は自動判定
- `--no-limit`: ページ数制限を無効にする (注意: 大量のページがある場合は時間がかかります)
- `--pages-per-file`: 1ファイルあたりのページ数 (デフォルト: 80) NotebookLMの制限に応じて調整
- `--javascript`: **🆕 JavaScript実行モードを有効** (SPA・動的サイト対応、処理時間が長くなります)
- `--exact-urls`: **🎯 NEW!** 指定URLのみを処理（リンク追跡なし、--url-listと組み合わせ必須）
- `--generate-sitemap`: **🗺️ NEW!** サイトマップ（URL・title・h1のリスト）を生成
- `--sitemap-format`: サイトマップの出力形式（csv または txt、デフォルト: csv）
- `--parallel-workers`: **⚡ NEW!** サイトマップ生成時の並列ワーカー数（1-20、デフォルト: 1=逐次処理）
- `--max-sitemap-pages`: **📊 NEW!** サイトマップ生成時の最大ページ数制限（テスト用、デフォルト: 無制限）
- `--save-progress`: **💾 NEW!** プログレス保存ファイル名（例: progress.json）
- `--resume-from`: **🔄 NEW!** プログレスファイルから再開（例: progress.json）

**注意**: 
- `url` と `--url-list` は排他的です。いずれか一方を必ず指定してください。
- `--exact-urls` は `--url-list` と組み合わせてのみ使用できます。
- `--generate-sitemap` は単一URLでのみ使用できます（--url-listや--exact-urlsと同時使用不可）。

## 📄 出力ファイル

### 単一サイトの場合
```
{ドメイン名}_{パス名}_all_content_{日時}_part1_of_9.txt
{ドメイン名}_{パス名}_all_content_{日時}_part2_of_9.txt
...
```

### 複数サイトの場合（🆕）
```
# 下位ページ自動収集モード（デフォルト）
multi_site_content_{日時}_part1_of_15.txt
multi_site_content_{日時}_part2_of_15.txt
...

# 指定URL限定モード（--exact-urls使用時）
exact_urls_content_{日時}_part1_of_5.txt
exact_urls_content_{日時}_part2_of_5.txt
...
```

### サイトマップの場合（🗺️ NEW!）
```
# CSV形式
{ドメイン名}_{パス名}_sitemap_{日時}.csv

# TXT形式
{ドメイン名}_{パス名}_sitemap_{日時}.txt
```

**サイトマップCSV形式の例:**
```csv
URL,Title,H1,Status
https://example.com/,Example Site - ホーム,ようこそ,success
https://example.com/about,会社概要,私たちについて,success
https://example.com/contact,お問い合わせ,お気軽にご連絡ください,success
```

## 📊 分割について
- **デフォルト**: 80ページずつ分割
- **NotebookLM対応**: 各ファイルがNotebookLMの制限内に収まるサイズ
- **調整可能**: `--pages-per-file` オプションで分割サイズを変更

## ⚙️ 動作について

### 📋 処理フロー
1. **事前探索**: まず全ページのURLを収集して総ページ数を表示
2. **処理計画表示**: 実際に処理するページ数と推定時間を表示
3. **テキスト抽出**: 各ページからコンテンツを抽出
   - **標準モード**: HTTPリクエスト → HTML解析 → テキスト抽出
   - **JavaScriptモード**: ブラウザ起動 → ページ読み込み → JS実行 → DOM取得 → テキスト抽出

### 🔄 JavaScript実行モードについて

#### 使用する場面
- **取得したテキストが不完全な場合**
- API仕様書サイト（例：Chatwork、Stripe、GitHub API等）
- 現代的なWebアプリ
- 「Loading...」や「読み込み中...」しか表示されない場合

#### 技術的な仕組み
- **Selenium + ChromeDriver**を使用
- 実際のブラウザでページを開きJavaScriptを実行
- DOM操作完了後のHTMLを取得
- 従来と同じBeautifulSoupで解析

#### パフォーマンス比較
| 項目 | 標準モード | JavaScript実行モード |
|------|-----------|-------------------|
| **処理速度** | 🚀 高速（1-2秒/ページ） | 🐌 低速（3-5秒/ページ） |
| **メモリ使用量** | 💾 軽量（10-50MB） | 🐘 重量（100-300MB） |
| **適用サイト** | 静的サイト | SPA・動的サイト |
| **精度** | ✅ 確実（静的コンテンツ） | ✅ 確実（動的コンテンツ） |

### 対象となるページ
- 同一ドメイン内のHTMLページのみ
- **指定されたURL配下のパス階層のみ**: 例えば `https://example.com/docs/api/` を指定した場合、`/docs/api/` 配下のページのみが対象
- **ベースパス手動指定**: `--base-path` オプションで範囲を調整可能
  - より広い範囲: `--base-path "/docs/"` で `/docs/` 配下全体
  - より狭い範囲: `--base-path "/docs/api/v2/"` で特定のサブディレクトリのみ
- `robots.txt`には対応していないため、必要に応じて手動で確認してください

### 除外される要素
- **ファイル**: PDF、画像、動画、Office文書など
- **パス**: `/admin/`, `/api/`, `/wp-admin/`, `/login/`, `/logout/`
- **HTML要素**: `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, `<aside>`

### サーバー負荷対策
- デフォルトで1秒間隔でのリクエスト
- JavaScript実行モードでは3秒以上の間隔を推奨
- 適切なUser-Agentの設定
- タイムアウト設定（30秒）

## 💡 NotebookLMでの使用方法

1. このツールでWebサイトのテキストを抽出（複数ファイルで出力）
2. 生成された `.txt` ファイルを**すべて**NotebookLMにアップロード
   - パート1から順番にアップロードすることをおすすめします
   - 一度に複数ファイルを選択してアップロード可能
3. サイト全体の内容について質問・分析が可能

### 📋 分割ファイルのメリット
- **NotebookLMの制限回避**: 大きなサイトでも確実に読み込める
- **段階的アップロード**: 必要な部分だけ先にアップロード可能
- **エラー回避**: 1つのファイルでエラーが出ても他は正常に処理

## ⚠️ 注意事項

- **利用規約の確認**: スクレイピング対象サイトの利用規約・robots.txtを事前に確認してください
- **適切な間隔**: サーバーに負荷をかけないよう、適切な遅延時間を設定してください
  - JavaScript実行モードでは特に長めの間隔（3秒以上）を推奨
- **個人利用**: 商用利用や大規模なスクレイピングは避けてください
- **著作権**: 抽出したコンテンツの著作権にご注意ください
- **リソース使用量**: JavaScript実行モードは多くのメモリとCPUを使用します
  - 並列処理時は使用リソースが並列数に比例して増加します（5並列 = 5倍のメモリ使用量）
  - メモリ不足時は並列数を減らすか、`--max-sitemap-pages`でページ数を制限してください

## 🔧 トラブルシューティング

### よくあるエラー

**接続エラー**
```
requests.exceptions.ConnectionError
```
- ネットワーク接続を確認
- URLが正しいか確認

**タイムアウトエラー**
```
requests.exceptions.Timeout
```
- 遅延時間を増やしてみる: `--delay 3.0`
- JavaScript実行モードの場合は: `--delay 5.0`

**アクセス拒否**
```
403 Forbidden
```
- サイトがスクレイピングを制限している可能性
- robots.txtや利用規約を確認

**ChromeDriverエラー（JavaScript実行モード）**
```
WebDriverException
```
- ChromeDriverが自動ダウンロードされるまで待機
- Chromeブラウザがインストールされているか確認
- `uv cache clean` でキャッシュをクリア後、`uv sync` で再インストール

**取得したテキストが不完全**
- 動的サイトの可能性：`--javascript` オプションを試す
- 遅延時間を増やす：`--delay 3.0`

## 🤝 ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 📋 使用例

### 🔗 複数サイト処理（新機能）

```bash
# 複数のAPIドキュメントサイトを一括処理（下位ページも自動収集）
python main.py --url-list api_docs.txt --javascript --delay 2.0

# CSVから技術文書サイトを処理（各サイト50ページまで）
python main.py --url-list tech_sites.csv --max-pages 50 --delay 1.5

# 🎯 指定されたURLのみを処理（リンク追跡なし）- NEW!
python main.py --url-list specific_pages.txt --exact-urls --javascript

# 制限なしで複数サイトを徹底的に処理（注意：時間がかかります）
python main.py --url-list sites.txt --no-limit --delay 3.0
```

**URLリストファイルの例（api_docs.txt）:**
```
https://developer.chatwork.com/reference/
https://stripe.com/docs/api
https://docs.github.com/en/rest
https://developer.twitter.com/en/docs/api
```

**URLリストファイルの例（tech_sites.csv）:**
```csv
url,site_name,category
https://docs.python.org/3/,Python Official Docs,Programming
https://developer.mozilla.org/en-US/docs/Web/,MDN Web Docs,Web Development
https://kubernetes.io/docs/,Kubernetes Docs,DevOps
https://docs.docker.com/,Docker Docs,DevOps
```

**指定URL限定モード用の例（specific_pages.txt）:**
```
https://api.example.com/docs/authentication
https://api.example.com/docs/users
https://api.example.com/docs/orders
https://api.example.com/docs/payments
https://blog.example.com/important-post-1
https://blog.example.com/important-post-2
```

### 🗺️ サイトマップ生成（NEW!）

```bash
# 基本的なサイトマップ生成（CSV形式）
python main.py https://example.com --generate-sitemap

# TXT形式でサイトマップ生成
python main.py https://example.com --generate-sitemap --sitemap-format txt

# JavaScript対応でサイトマップ生成（SPA向け）
python main.py https://api.docs-site.com --generate-sitemap --javascript --delay 2.0

# 特定パス配下のみサイトマップ生成
python main.py https://docs.example.com/api/ --generate-sitemap --base-path "/api/"

# より慎重にサイトマップ生成
python main.py https://example.com --generate-sitemap --delay 3.0

# ⚡ 高速化：並列処理（5ワーカー）
python main.py https://example.com --generate-sitemap --parallel-workers 5

# 📊 テスト用：ページ数制限
python main.py https://example.com --generate-sitemap --max-sitemap-pages 1000

# 💾 大規模サイト対応：プログレス保存
python main.py https://example.com --generate-sitemap --save-progress progress.json

# 🔄 中断時：プログレス再開
python main.py https://example.com --generate-sitemap --resume-from progress.json

# 🚀 最高速設定：並列処理+制限+保存
python main.py https://example.com --generate-sitemap --parallel-workers 5 --max-sitemap-pages 5000 --save-progress progress.json
```

### 単一サイト処理（従来の機能）

```bash
# 基本的な使用方法（自動でベースパス判定）
python main.py https://example.com

# Google Cloud Docsの特定セクションのみ対象（自動判定）
python main.py "https://cloud.google.com/run/docs/fit-for-run?hl=ja"
# → /run/docs/ 配下のページのみが対象になります

# ベースパスを手動指定（より広い範囲を対象）
python main.py "https://cloud.google.com/run/docs/fit-for-run?hl=ja" --base-path "/run/"
# → /run/ 配下の全てのページが対象になります

# ベースパスを手動指定（より狭い範囲を対象）
python main.py "https://cloud.google.com/run/docs/" --base-path "/run/docs/concepts/"
# → /run/docs/concepts/ 配下のページのみが対象になります

# ページ数制限を外して全てのページを取得
python main.py "https://cloud.google.com/run/docs/fit-for-run?hl=ja" --no-limit
# → 見つかる限り全てのページを取得します

# 分割サイズを調整（50ページずつ分割）
python main.py "https://cloud.google.com/run/docs/fit-for-run?hl=ja" --pages-per-file 50
# → NotebookLMでより細かく分析したい場合

# 大きめに分割（120ページずつ）
python main.py "https://cloud.google.com/run/docs/fit-for-run?hl=ja" --pages-per-file 120
# → 各ファイルをより大きくしたい場合（制限に注意）

# より慎重に（50ページまで、2秒間隔）
python main.py https://example.com --max-pages 50 --delay 2.0
```

### 使い分けの目安

```bash
# 🗺️ サイト構造を把握したい場合 - NEW!
python main.py https://target-site.com --generate-sitemap

# 🔗 複数の関連サイトを統合分析したい場合（下位ページ自動収集）
python main.py --url-list related_sites.txt

# 🎯 特定のページのみを厳選して分析したい場合 - NEW!
python main.py --url-list specific_pages.txt --exact-urls

# 📍 特定サイトを詳細に分析したい場合  
python main.py https://target-site.com/docs/

# ⚡ まず標準モードで試す（高速）
python main.py --url-list sites.txt

# 🌐 取得したテキストが不完全だった場合、JavaScript実行モードで再試行
python main.py --url-list sites.txt --javascript --delay 3.0
```

## 🔄 複数サイト処理の動作について

### 📊 処理フロー

#### 🌐 下位ページ自動収集モード（デフォルト）
1. **URLリスト読み込み**: txt/csvファイルからURLリストを抽出
2. **サイト別処理**: 各URLを個別にスクレイピング（既存ロジックを使用）
3. **コンテンツ統合**: 全サイトのコンテンツを1つのリストに統合
4. **分割保存**: NotebookLM制限に応じて複数ファイルに分割保存

#### 🎯 指定URL限定モード（--exact-urls）- NEW!
1. **URLリスト読み込み**: txt/csvファイルからURLリストを抽出
2. **個別ページ処理**: 各URLのページのみを取得（リンク追跡なし）
3. **コンテンツ統合**: 指定された全ページのコンテンツを統合
4. **分割保存**: NotebookLM制限に応じて複数ファイルに分割保存

### 🎯 適用場面

#### 🌐 下位ページ自動収集モード
- **競合他社分析**: 複数の競合サイトを一括で情報収集
- **技術調査**: 複数のAPIドキュメント・技術文書を統合分析
- **市場調査**: 複数のニュースサイト・ブログを一括収集
- **学術研究**: 複数の研究機関サイトから情報収集

#### 🎯 指定URL限定モード（NEW!）
- **厳選ページ分析**: 意味的に重要なページのみを集中分析
- **特定記事収集**: ブログ記事やニュース記事の特定URLのみを収集
- **階層構造無視**: URLパス構造と内容の意味構造が一致しないサイト対応
- **ピンポイント調査**: API仕様書の特定エンドポイントのみを調査

#### 🗺️ サイトマップ生成モード（NEW!）
- **サイト構造把握**: 全ページのURL・タイトル・見出しを一覧化
- **コンテンツ企画**: 既存コンテンツの構成を参考にした新規企画
- **SEO分析**: タイトルタグとH1タグの最適化検討
- **サイト監査**: 全ページの情報を俯瞰的にチェック
- **リンク構造分析**: サイト内のページ間関係を把握

### ⚙️ 処理時間の目安

#### 🌐 下位ページ自動収集モード
- **txtリスト（5サイト、各100ページ）**: 約8-15分（標準モード）
- **txtリスト（5サイト、各100ページ）**: 約25-40分（JavaScriptモード）

#### 🎯 指定URL限定モード
- **txtリスト（20URL）**: 約30秒-2分（標準モード）
- **txtリスト（20URL）**: 約2-5分（JavaScriptモード）

#### 🗺️ サイトマップ生成モード
- **中規模サイト（50ページ）**: 約1-3分（標準モード）
- **大規模サイト（3800ページ）**: 6-8時間（最適化前：12時間+）
- **並列処理5ワーカー**: **約3-5倍高速化**
- **ページ数制限（1000ページ）**: 約1-2時間
- **中規模サイト（50ページ）**: 約3-8分（JavaScriptモード）
- **大規模サイト（200ページ）**: 約5-12分（標準モード）

#### 共通設定
- **サイト間間隔**: 通常の遅延時間の2倍（サーバー負荷軽減）

## 🚀 サイトマップ生成の最適化機能（NEW!）

### ⚡ 並列処理機能
**概要**: 複数のページを同時に処理して大幅な高速化を実現

```bash
# 基本（逐次処理）
python main.py https://example.com --generate-sitemap

# 5ワーカーで並列処理（約5倍高速化）
python main.py https://example.com --generate-sitemap --parallel-workers 5

# 最大ワーカー数（20まで設定可能）
python main.py https://example.com --generate-sitemap --parallel-workers 10
```

**効果**:
- **3-5倍の高速化**: 5ワーカーで理論上5倍の処理速度
- **大規模サイト対応**: 3800ページの処理時間を12時間→3-4時間に短縮
- **スケーラブル**: サイトの規模に応じてワーカー数を調整可能

**⚠️ メモリ負荷について**:
- **静的モード**: 1ワーカーあたり約10-20MB（軽量）
- **JavaScriptモード**: 1ワーカーあたり約100-300MB（Chrome起動のため重量）

**推奨並列数**:
```bash
# メモリ8GB以下の環境
--parallel-workers 2  # JavaScript使用時
--parallel-workers 5  # 静的モード時

# メモリ16GB以上の環境  
--parallel-workers 5  # JavaScript使用時
--parallel-workers 10 # 静的モード時
```

**注意**: JavaScriptモードでは各ワーカーが独立したChromeブラウザを起動するため、5並列=Chrome5個同時実行と同等の負荷がかかります。

### 📊 ページ数制限機能
**概要**: 大規模サイトのテストや段階的処理に最適

```bash
# 100ページまでテスト
python main.py https://example.com --generate-sitemap --max-sitemap-pages 100

# 1000ページで実用テスト
python main.py https://example.com --generate-sitemap --max-sitemap-pages 1000

# 並列処理と組み合わせ
python main.py https://example.com --generate-sitemap --parallel-workers 5 --max-sitemap-pages 2000
```

**用途**:
- **事前テスト**: 本格実行前の動作確認
- **段階的処理**: まず少量で試してから全体処理
- **リソース制限**: メモリやディスク容量が限られた環境

### 💾 プログレス保存・再開機能
**概要**: 大規模サイトの処理中断時にも安心

```bash
# プログレス保存付きで実行
python main.py https://example.com --generate-sitemap --save-progress progress.json

# 中断した処理を再開
python main.py https://example.com --generate-sitemap --resume-from progress.json

# 並列処理+プログレス保存
python main.py https://example.com --generate-sitemap --parallel-workers 5 --save-progress progress.json
```

**特徴**:
- **自動保存**: 50ページごとに進捗を自動保存
- **完全再開**: 中断地点から正確に処理を再開
- **安全性**: ネットワークエラーや電源断にも対応

### 🎯 推奨使用パターン

```bash
# ステップ1: 小規模テスト（速度確認）
python main.py https://example.com --generate-sitemap --max-sitemap-pages 100

# ステップ2: 中規模テスト（品質確認） 
python main.py https://example.com --generate-sitemap --parallel-workers 3 --max-sitemap-pages 1000

# ステップ3: 本格実行（大規模処理）
python main.py https://example.com --generate-sitemap --parallel-workers 5 --save-progress progress.json

# 緊急時: 中断からの再開
python main.py https://example.com --generate-sitemap --resume-from progress.json
```

### 📈 性能比較表

| 設定 | 処理方式 | 3800ページの処理時間 | 高速化率 | メモリ使用量（目安） |
|------|----------|---------------------|----------|-------------------|
| デフォルト | 逐次処理 | 約6-8時間 | 基準 | 50-100MB |
| `--parallel-workers 3` | 3並列処理 | 約2-3時間 | **3倍高速化** | 150-900MB* |
| `--parallel-workers 5` | 5並列処理 | 約1.5-2時間 | **4-5倍高速化** | 250-1500MB* |
| `--max-sitemap-pages 1000` | 制限付き処理 | 約20-30分 | **制限内で完了** | 制限に応じて削減 |

*JavaScriptモード使用時は上限値、静的モードは下限値程度

## 💡 NotebookLMでの使用方法

1. このツールでWebサイトのテキストを抽出（複数ファイルで出力）
2. 生成された `.txt` ファイルを**すべて**NotebookLMにアップロード
   - パート1から順番にアップロードすることをおすすめします
   - 一度に複数ファイルを選択してアップロード可能
3. サイト全体の内容について質問・分析が可能

### 📋 分割ファイルのメリット
- **NotebookLMの制限回避**: 大きなサイトでも確実に読み込める
- **段階的アップロード**: 必要な部分だけ先にアップロード可能
- **エラー回避**: 1つのファイルでエラーが出ても他は正常に処理

## ⚠️ 注意事項

- **利用規約の確認**: スクレイピング対象サイトの利用規約・robots.txtを事前に確認してください
- **適切な間隔**: サーバーに負荷をかけないよう、適切な遅延時間を設定してください
  - JavaScript実行モードでは特に長めの間隔（3秒以上）を推奨
- **個人利用**: 商用利用や大規模なスクレイピングは避けてください
- **著作権**: 抽出したコンテンツの著作権にご注意ください
- **リソース使用量**: JavaScript実行モードは多くのメモリとCPUを使用します

## 🔧 トラブルシューティング

### よくあるエラー

**接続エラー**
```
requests.exceptions.ConnectionError
```
- ネットワーク接続を確認
- URLが正しいか確認

**タイムアウトエラー**
```
requests.exceptions.Timeout
```
- 遅延時間を増やしてみる: `--delay 3.0`
- JavaScript実行モードの場合は: `--delay 5.0`

**アクセス拒否**
```
403 Forbidden
```
- サイトがスクレイピングを制限している可能性
- robots.txtや利用規約を確認

**ChromeDriverエラー**
```
selenium.common.exceptions.WebDriverException
```
- Chromeブラウザがインストールされているか確認
- ChromeDriverが自動更新されるまで少し待つ

**メモリ不足**
```
MemoryError
```
- `--max-pages` でページ数を制限
- `--pages-per-file` で分割サイズを小さく

## 📄 ライセンス

MIT License