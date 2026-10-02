# TODO.md: 実装タスク分解リスト

## Phase 1: 基盤環境とデータストアの整備
- [x] 1.1 プロジェクト初期化
  - [x] `uv init` による `pyproject.toml` 作成と基本パッケージのインストール (`feedparser`, `sentence-transformers`, `numpy`, `rfeed`, `python-dateutil`)
  - [x] ディレクトリ作成 (`src/`, `data/`, `docs/`)
- [x] 1.2 設定ファイル `src/config.py` の実装
  - [x] 各種ファイルパス、モデル名、スコアしきい値定数の定義
- [x] 1.3 データベース層 `src/db.py` の実装
  - [x] SQLite接続ハンドラの作成
  - [x] `feeds`, `articles`, `bookmarks` のテーブル初期化クエリ実装
  - [x] 記事の重複チェック挿入（GUIDベース）機能の実装

---

## Phase 2: データ取り込みとベクトル化
- [x] 2.1 OPMLインポーター `src/opml_loader.py` の実装
  - [x] `data/seeds.opml` を読み込み、`feeds` テーブルへ初期URLを一括登録するスクリプト
- [x] 2.2 エンベッダー `src/embedder.py` の実装
  - [x] `sentence-transformers` モデルのロードとキャッシュ処理
  - [x] 単一テキストおよびバッチテキストのベクトル生成メソッド
- [x] 2.3 ブックマークプロファイル同期
  - [x] `data/bookmarks.txt` の差分検知とベクトルキャッシュ更新
  - [x] 重み付け平均による「統合ユーザー関心ベクトル」生成ロジックの実装

---

## Phase 3: クロール・スコアリング・刈り取り
- [x] 3.1 クローラー `src/crawler.py` の実装
  - [x] `feeds` テーブルからアクティブなフィードを並行/順次取得
  - [x] `feedparser` による記事パース、最新記事の抽出
  - [x] 取得記事を未評価状態で `articles` テーブルに保存
- [x] 3.2 スコアラー `src/scorer.py` の実装
  - [x] 未評価記事のベクトル化とユーザー関心ベクトルとのコサイン類似度計算
  - [x] しきい値判定と `is_curated` フラグ、スコアの永続化
- [x] 3.3 フィードプルーナー `src/pruner.py` の実装
  - [x] フィード単位のヒット率（採用数 / 取得総数）の集計
  - [x] 低ヒット率フィードのステータス変更（`dormant` 化）ロジック

---

## Phase 4: フィード生成とパイプライン統合
- [x] 4.1 RSS生成器 `src/generator.py` の実装
  - [x] `is_curated = 1` かつ直近の記事をクエリ
  - [x] `rfeed` を利用して `docs/curated.xml` に有効なRSS 2.0を出力
- [x] 4.2 パイプラインオーケストレーター `src/main.py` の実装
  - [x] 引数処理（`--import-opml`, `--update-bookmarks`, `--run`）
  - [x] 全体のシーケンス制御（ブックマーク更新 -> クロール -> 判定 -> プルーニング -> XML出力）
- [x] 4.3 動作確認とテスト
  - [x] サンプルOPMLとダミーのブックマークを用いたエンドツーエンド実行テスト
  - [x] 生成された `docs/curated.xml` の妥当性確認