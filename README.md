# NotebookLM用 Webサイト一括テキスト抽出ツール

指定されたWebサイトの全ページからテキストを抽出し、NotebookLMで読み込みやすい1つのテキストファイルにまとめるPythonツールです。

## 🎯 主な機能

- **単一サイト処理**: 指定されたWebサイトのドメイン内の全ページを自動収集
- **🆕 複数サイト処理**: URLリストファイル（txt/csv）から複数サイトを一括処理
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
# txtファイルから複数サイトを処理
python main.py --url-list sites.txt

# csvファイルから複数サイトを処理
python main.py --url-list sites.csv --javascript --delay 2.0
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

**注意**: `url` と `--url-list` は排他的です。いずれか一方を必ず指定してください。

## 📄 出力ファイル

### 単一サイトの場合
```
{ドメイン名}_{パス名}_all_content_{日時}_part1_of_9.txt
{ドメイン名}_{パス名}_all_content_{日時}_part2_of_9.txt
...
```

### 複数サイトの場合（🆕）
```
multi_site_content_{日時}_part1_of_15.txt
multi_site_content_{日時}_part2_of_15.txt
...
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
# 複数のAPIドキュメントサイトを一括処理
python main.py --url-list api_docs.txt --javascript --delay 2.0

# CSVから技術文書サイトを処理（各サイト50ページまで）
python main.py --url-list tech_sites.csv --max-pages 50 --delay 1.5

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
# 🔗 複数の関連サイトを統合分析したい場合
python main.py --url-list related_sites.txt

# 📍 特定サイトを詳細に分析したい場合  
python main.py https://target-site.com/docs/

# ⚡ まず標準モードで試す（高速）
python main.py --url-list sites.txt

# 🌐 取得したテキストが不完全だった場合、JavaScript実行モードで再試行
python main.py --url-list sites.txt --javascript --delay 3.0
```

## 🔄 複数サイト処理の動作について

### 📊 処理フロー
1. **URLリスト読み込み**: txt/csvファイルからURLリストを抽出
2. **サイト別処理**: 各URLを個別にスクレイピング（既存ロジックを使用）
3. **コンテンツ統合**: 全サイトのコンテンツを1つのリストに統合
4. **分割保存**: NotebookLM制限に応じて複数ファイルに分割保存

### 🎯 適用場面
- **競合他社分析**: 複数の競合サイトを一括で情報収集
- **技術調査**: 複数のAPIドキュメント・技術文書を統合分析
- **市場調査**: 複数のニュースサイト・ブログを一括収集
- **学術研究**: 複数の研究機関サイトから情報収集

### ⚙️ 処理時間の目安
- **txtリスト（5サイト、各100ページ）**: 約8-15分（標準モード）
- **txtリスト（5サイト、各100ページ）**: 約25-40分（JavaScriptモード）
- **サイト間間隔**: 通常の遅延時間の2倍（サーバー負荷軽減）