from contextlib import contextmanager
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple
from src.config import DB_PATH


@contextmanager
def get_connection(db_path: Path | str = DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """SQLite接続を取得するコンテキストマネージャ。親ディレクトリが存在しない場合は作成し、終了時にクローズする。"""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: Path | str = DB_PATH) -> None:
    """テーブル定義を作成・初期化する。"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # テーブル: feeds
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                status TEXT CHECK(status IN ('active', 'dormant', 'disabled')) DEFAULT 'active',
                total_fetched INTEGER DEFAULT 0,
                hit_count INTEGER DEFAULT 0,
                last_fetched_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # テーブル: articles
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_id INTEGER NOT NULL,
                guid TEXT UNIQUE NOT NULL,
                title TEXT,
                link TEXT,
                published_at DATETIME,
                content_snippet TEXT,
                similarity_score REAL,
                is_curated BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (feed_id) REFERENCES feeds (id) ON DELETE CASCADE
            )
            """
        )

        # インデックス
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_guid ON articles(guid);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_is_curated ON articles(is_curated);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);")

        # テーブル: bookmarks
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT UNIQUE NOT NULL,
                embedding BLOB,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def add_feed(url: str, title: Optional[str] = None, db_path: Path | str = DB_PATH) -> Optional[int]:
    """
    フィードを登録する。既に存在する場合は何もしない。
    登録されたfeedのid（または既存feedのid）を返す。
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO feeds (url, title, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title = COALESCE(excluded.title, feeds.title)
            RETURNING id
            """,
            (url, title, datetime.now().isoformat()),
        )
        row = cursor.fetchone()
        conn.commit()
        return row[0] if row else None


def insert_article(
    feed_id: int,
    guid: str,
    title: str,
    link: str,
    published_at: Optional[str],
    content_snippet: str,
    db_path: Path | str = DB_PATH,
) -> bool:
    """
    記事を重複チェック（GUIDユニーク）付きで挿入する。
    挿入に成功した場合は True、既に存在していた場合は False を返す。
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO articles (feed_id, guid, title, link, published_at, content_snippet, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feed_id,
                    guid,
                    title,
                    link,
                    published_at,
                    content_snippet,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # 重複記事（guidが既に存在）
            return False


def get_feeds(status: Optional[str] = None, db_path: Path | str = DB_PATH) -> List[sqlite3.Row]:
    """フィード一覧を取得する。"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM feeds WHERE status = ? ORDER BY id ASC", (status,))
        else:
            cursor.execute("SELECT * FROM feeds ORDER BY id ASC")
        return cursor.fetchall()


def update_feed_stats(
    feed_id: int,
    fetched_increment: int = 0,
    hit_increment: int = 0,
    last_fetched_at: Optional[str] = None,
    db_path: Path | str = DB_PATH,
) -> None:
    """フィードの取得総数、ヒット数、最終フェッチ日時を更新する。"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE feeds
            SET total_fetched = total_fetched + ?,
                hit_count = hit_count + ?,
                last_fetched_at = COALESCE(?, last_fetched_at)
            WHERE id = ?
            """,
            (fetched_increment, hit_increment, last_fetched_at, feed_id),
        )
        conn.commit()


def update_feed_status(feed_id: int, status: str, db_path: Path | str = DB_PATH) -> None:
    """フィードのステータス（active, dormant, disabled）を更新する。"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE feeds SET status = ? WHERE id = ?", (status, feed_id))
        conn.commit()


def get_unscored_articles(db_path: Path | str = DB_PATH) -> List[sqlite3.Row]:
    """類似度スコアが未計算（NULL）の記事を取得する。"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, feed_id, guid, title, link, published_at, content_snippet
            FROM articles
            WHERE similarity_score IS NULL
            ORDER BY id ASC
            """
        )
        return cursor.fetchall()


def update_article_score(
    article_id: int,
    score: float,
    is_curated: bool,
    db_path: Path | str = DB_PATH,
) -> None:
    """記事の類似度スコアと採用フラグを更新する。"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE articles
            SET similarity_score = ?,
                is_curated = ?
            WHERE id = ?
            """,
            (score, 1 if is_curated else 0, article_id),
        )
        conn.commit()


def get_curated_articles(
    days_limit: int = 7,
    max_items: int = 50,
    db_path: Path | str = DB_PATH,
) -> List[sqlite3.Row]:
    """直近採用記事を取得する（スコア降順、公開日降順）。"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, feed_id, guid, title, link, published_at, content_snippet, similarity_score
            FROM articles
            WHERE is_curated = 1
              AND (
                  published_at >= datetime('now', '-' || ? || ' days')
                  OR created_at >= datetime('now', '-' || ? || ' days')
              )
            ORDER BY similarity_score DESC, published_at DESC
            LIMIT ?
            """,
            (days_limit, days_limit, max_items),
        )
        return cursor.fetchall()


def get_bookmarks(db_path: Path | str = DB_PATH) -> List[sqlite3.Row]:
    """保存済みブックマークを取得する。"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, text, embedding, added_at FROM bookmarks ORDER BY id ASC")
        return cursor.fetchall()


def upsert_bookmark(
    text: str,
    embedding: Optional[bytes] = None,
    added_at: Optional[str] = None,
    db_path: Path | str = DB_PATH,
) -> int:
    """ブックマークを登録または更新する。"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO bookmarks (text, embedding, added_at)
            VALUES (?, ?, COALESCE(?, CURRENT_TIMESTAMP))
            ON CONFLICT(text) DO UPDATE SET
                embedding = COALESCE(excluded.embedding, bookmarks.embedding)
            RETURNING id
            """,
            (text, embedding, added_at),
        )
        row = cursor.fetchone()
        conn.commit()
        return row[0]
