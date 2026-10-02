# SPEC.md: 自律型パーソナルRSSキュレーションエンジン

## 1. 概要
登録された大量のRSSフィードから記事を定期巡回し、ユーザーの「関心記事（Bookmark / Read）」とのベクトル類似度（Embedding）を算出。高スコア記事のみを抽出した専用RSSフィード（`curated.xml`）を生成・公開するローカル駆動型キュレーションシステム。
低エンゲージメントなフィードの自動休眠（Pruning）機構を備え、最終的なXMLはGitHub Pages等でホストして任意のRSSリーダーから購読可能にする。

---

## 2. システム要件 & 制約
- **実行環境:** WSL2 (Ubuntu / Debian系 Linux)
- **言語・パッケージ管理:** Python 3.11+ / `uv` (または `pixi`)
- **推論方式:** 完全ローカル動作（ローカルEmbeddingモデル使用、API課金ゼロ）
- **DB:** SQLite3（標準ライブラリ、外部DBサーバー不要）
- **出力形態:** 静的RSS 2.0 / Atom XMLファイル（`docs/curated.xml`）

---

## 3. ディレクトリ構成
rss-curator/
├── pyproject.toml
├── README.md
├── SPEC.md
├── TODO.md
├── data/
│   ├── curator.db          # フィード一覧、記事履歴、ベクトルキャッシュ
│   ├── bookmarks.txt       # ユーザーが「面白かった」と感じた記事タイトル・要約・URL
│   └── seeds.opml          # 初期のFeedly等からエクスポートしたOPML
├── docs/
│   └── curated.xml         # GitHub Pages公開用RSS出力先
└── src/
    ├── __init__.py
    ├── config.py           # しきい値、モデル名、パス等の設定値
    ├── db.py               # SQLite接続・テーブル初期化・CRUD
    ├── embedder.py         # sentence-transformersによるベクトル化
    ├── opml_loader.py      # OPMLインポート・フィード登録
    ├── crawler.py          # feedparserによる未読記事フェッチ
    ├── scorer.py           # コサイン類似度計算・時間減衰計算
    ├── pruner.py           # フィードのヒット率計算・休眠フラグ更新
    ├── generator.py        # RSS (XML) 生成
    └── main.py             # パイプライン実行オーケストレーター

---

## 4. 依存ライブラリとインストール手順
`uv` を用いた環境セットアップコマンド：

$ uv init rss-curator
$cd rss-curator$ uv add feedparser sentence-transformers numpy rfeed python-dateutil requests

主要ライブラリの用途：
- `feedparser`: RSS/Atomフィードのパース
- `sentence-transformers`: 多言語対応ローカル埋め込みモデル（例: `paraphrase-multilingual-MiniLM-L12-v2` または日本語特化モデル）
- `numpy`: ベクトル演算およびコサイン類似度計算
- `rfeed`: 軽量なRSS 2.0フィードXML生成ライブラリ
- `python-dateutil`: フィードごとの不規則な日付パース

---

## 5. データモデル設計 (SQLite)

### テーブル: `feeds`
- `id` (INTEGER PK AUTOINCREMENT)
- `url` (TEXT UNIQUE)
- `title` (TEXT)
- `status` (TEXT: 'active' | 'dormant' | 'disabled') DEFAULT 'active'
- `total_fetched` (INTEGER) DEFAULT 0
- `hit_count` (INTEGER) DEFAULT 0      # 類似度しきい値を超えた記事数
- `last_fetched_at` (DATETIME)
- `created_at` (DATETIME)

### テーブル: `articles`
- `id` (INTEGER PK AUTOINCREMENT)
- `feed_id` (INTEGER FK)
- `guid` (TEXT UNIQUE)
- `title` (TEXT)
- `link` (TEXT)
- `published_at` (DATETIME)
- `content_snippet` (TEXT)
- `similarity_score` (REAL)
- `is_curated` (BOOLEAN) DEFAULT 0
- `created_at` (DATETIME)

### テーブル: `bookmarks`
- `id` (INTEGER PK AUTOINCREMENT)
- `text` (TEXT)                       # 記事のタイトル＋抜粋
- `embedding` (BLOB)                  # ベクトルバイナリ（キャッシュ）
- `added_at` (DATETIME)

---

## 6. コアロジック仕様

### 6.1 ベクトル埋め込み & プロファイル作成 (`embedder.py`)
1. デフォルトモデル: `paraphrase-multilingual-MiniLM-L12-v2`（軽量・CPU/GPU問わず高速・多言語対応）
2. `data/bookmarks.txt` に記載された各行（または各ブロック）を読み込み、ベクトル化。
3. **時間減衰（Time Decay）**:
   - ブックマークが追加された日時に応じて重みを付与（直近ほど高いウェイト）。
   - 統合ユーザー関心ベクトル V_user = sum(w_i * v_i)（正規化済み）を算出。

### 6.2 スコアリング & 抽出 (`scorer.py`)
1. クロールした各未読記事の `title + " " + content_snippet` をベクトル化し v_art を生成。
2. コサイン類似度 sim = (v_art・V_user) / (||v_art|| * ||V_user||) を計算。
3. `config.SIMILARITY_THRESHOLD`（例: 0.65）以上の記事を「Curated（採用）」と判定。
4. 採用記事は `articles.is_curated = 1` とし、該当フィードの `hit_count` を加算。

### 6.3 フィード刈り取り（Pruning）ロジック (`pruner.py`)
- 条件: `total_fetched >= 50` かつ `(hit_count / total_fetched) < 0.02`（ヒット率2%未満）
- 処理: `feeds.status` を `'dormant'` に変更し、クローラーの巡回頻度を通常の1/10に落とす（または除外する）。

### 6.4 フィード出力 (`generator.py`)
- 直近7日以内に採用（`is_curated = 1`）された記事をスコア降順・公開日降順でソートし、最大30〜50件で `docs/curated.xml` を書き出し。

---

## 7. 設定値 (`config.py`)
- `DB_PATH`: `data/curator.db`
- `BOOKMARKS_PATH`: `data/bookmarks.txt`
- `OUTPUT_FEED_PATH`: `docs/curated.xml`
- `SIMILARITY_THRESHOLD`: `0.65` (チューニング可能)
- `FEED_TITLE`: "Personal Tailored Feed"
- `FEED_LINK`: "https://<your-username>.github.io/<repo-name>/curated.xml"