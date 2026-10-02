# 自律型パーソナルRSSキュレーションエンジン (rss-curator)

登録された大量のRSSフィードから記事を巡回・収集し、ユーザーの関心記事（`data/bookmarks.txt`）とのローカルベクトル類似度（`sentence-transformers`）を計算して、関心度の高い記事のみを抽出したパーソナライズRSSフィード（`docs/curated.xml`）を生成・公開するシステムです。

## 主な特徴
- **完全ローカル推論**: `sentence-transformers`（多言語対応モデル `paraphrase-multilingual-MiniLM-L12-v2`）によるローカルEmbedding算出。外部API課金ゼロ。
- **時間減衰（Time Decay）モデル**: ブックマーク追加日時を考慮し、直近の興味・関心トピックを高精度に反映。
- **自動休眠機構（Pruning）**: ヒット率の低いフィードを自動的に `dormant` 状態とし、無駄なクローリング負荷を軽減。
- **静的XML出力**: `docs/curated.xml` に標準RSS 2.0形式で出力。GitHub Pagesなどで簡単に配信・購読可能。

## ディレクトリ構成
```
rss-curator/
├── pyproject.toml
├── README.md
├── SPEC.md
├── TODO.md
├── data/
│   ├── curator.db          # SQLiteデータベース（フィード・記事・ベクトルキャッシュ）
│   ├── bookmarks.txt       # ユーザーの興味関心テキスト・ブックマーク一覧
│   └── seeds.opml          # 初期フィードリスト（OPML）
├── docs/
│   └── curated.xml         # 出力されるRSSフィード
├── src/
│   ├── config.py           # しきい値やパス等の設定値
│   ├── db.py               # SQLite接続・テーブル初期化・CRUD
│   ├── embedder.py         # ベクトル化・ブックマーク同期・ユーザーベクトル生成
│   ├── opml_loader.py      # OPMLインポート・フィード登録
│   ├── crawler.py          # feedparserによる記事取得
│   ├── scorer.py           # 類似度スコアリング & 採用判定
│   ├── pruner.py           # 低エンゲージメントフィードの休眠化
│   ├── generator.py        # RSS 2.0 XML生成
│   └── main.py             # パイプライン実行オーケストレーター
└── tests/                  # 各種単体・統合テスト
```

## クイックスタート

### 1. 依存関係のインストール
```bash
uv sync
```

### 2. フィードとブックマークの準備
- `data/seeds.opml`: 購読したいRSSフィードを記載（Feedly等からエクスポートしたファイルも可）
- `data/bookmarks.txt`: 興味のあるトピックや過去に面白かった記事タイトル・抜粋を1行ずつ記載

### 3. パイプラインの実行
```bash
# 全パイプライン（取り込み・クロール・スコアリング・刈り取り・XML生成）の一括実行
uv run python -m src.main --run

# または個別の処理を実行
uv run python -m src.main --import-opml
uv run python -m src.main --update-bookmarks
uv run python -m src.main --crawl
uv run python -m src.main --score
uv run python -m src.main --prune
uv run python -m src.main --generate
```

### 4. 日常の更新方法（手動更新 & GitHub プッシュ）

フィードの巡回・スコアリング・XML生成・GitHubへの自動プッシュをワンクリックで実行できます：

- **バッチファイル（Windows エクスプローラーからダブルクリック）**:
  `update.bat`
- **PowerShell からの実行**:
  ```powershell
  .\update.ps1
  ```
- **CLI から直接実行**:
  ```bash
  uv run python -m src.main --run --push
  ```

---

### 5. Windows タスクスケジューラによる完全自動化

毎朝決まった時刻にバックグラウンドで自動巡回＆GitHubプッシュを行い、Feedlyに最新記事を届ける設定が可能です（ポップアップ画面なしで静かに実行されます）。

```powershell
# 毎朝 07:00 に自動実行するタスクを登録（デフォルト）
.\setup_scheduler.ps1

# 実行時刻を指定して登録（例: 毎朝 08:30）
.\setup_scheduler.ps1 -Time "08:30"

# 登録状況・最終実行日時の確認
.\setup_scheduler.ps1 -Status

# 自動実行の解除（タスク削除）
.\setup_scheduler.ps1 -Remove
```
※実行ログは `data/scheduler.log` に自動保存されます。

---

### 6. テストの実行
```bash
uv run python -m unittest discover -s tests
```
