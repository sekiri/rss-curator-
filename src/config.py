import os
from pathlib import Path

# プロジェクトルートディレクトリ（srcの親ディレクトリ）
BASE_DIR = Path(__file__).resolve().parent.parent

# データおよび出力パス
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"

DB_PATH = DATA_DIR / "curator.db"
BOOKMARKS_PATH = DATA_DIR / "bookmarks.txt"
SEEDS_OPML_PATH = DATA_DIR / "seeds.opml"
OUTPUT_FEED_PATH = DOCS_DIR / "curated.xml"

# モデル設定
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# スコアリング設定（Max-similarity方式: 0.45〜0.50程度が最適）
SIMILARITY_THRESHOLD = 0.45
TIME_DECAY_HALF_LIFE_DAYS = 30.0  # ブックマークの時間減衰半減期（日）

# フィードプルーニング設定
PRUNE_MIN_FETCHED = 50
PRUNE_MIN_HIT_RATE = 0.02

# フィード出力設定
FEED_TITLE = "Personal Tailored Feed"
FEED_LINK = "https://sekiri.github.io/rss-curator-/curated.xml"
FEED_DESCRIPTION = "Curated RSS feed generated based on user interest embeddings"
CURATED_DAYS_LIMIT = 7
MAX_CURATED_ITEMS = 50
