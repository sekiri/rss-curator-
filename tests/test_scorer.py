import os
import tempfile
import unittest
from pathlib import Path

from src.db import add_feed, get_connection, init_db, insert_article
from src.embedder import sync_bookmarks
from src.scorer import score_articles


class TestScorer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.gettempdir()
        self.test_db = Path(self.temp_dir) / f"test_scorer_{os.getpid()}_{self._testMethodName}.db"
        self.test_bms = Path(self.temp_dir) / f"test_scorer_bms_{os.getpid()}_{self._testMethodName}.txt"
        if self.test_db.exists():
            try:
                os.remove(self.test_db)
            except OSError:
                pass
        init_db(self.test_db)

    def tearDown(self):
        for p in [self.test_db, self.test_bms]:
            if p.exists():
                try:
                    os.remove(p)
                except OSError:
                    pass

    def test_score_articles(self):
        # 1. ブックマークを設定（AI / LLM / 機械学習に関心）
        bm_content = """# Interested topics
Large language models, LLM agents, deep learning neural networks
Transformer architecture and vector similarity search
"""
        self.test_bms.write_text(bm_content, encoding="utf-8")
        sync_bookmarks(bookmarks_path=self.test_bms, db_path=self.test_db)

        # 2. フィードを追加
        feed_id = add_feed("https://example.com/ai_and_cooking.xml", title="Tech & Life", db_path=self.test_db)

        # 3. 関連度の高い記事と低い記事を挿入
        insert_article(
            feed_id=feed_id,
            guid="article-high-1",
            title="Building autonomous agents with Large Language Models and transformers",
            link="https://example.com/ai-1",
            published_at="2026-09-30T10:00:00",
            content_snippet="An in-depth guide on deploying LLM multi-agent systems and vector databases.",
            db_path=self.test_db,
        )
        insert_article(
            feed_id=feed_id,
            guid="article-low-1",
            title="How to bake homemade sourdough bread with yeast and flour",
            link="https://example.com/bake-1",
            published_at="2026-09-30T11:00:00",
            content_snippet="Follow these easy steps to make delicious artisan sourdough bread at home.",
            db_path=self.test_db,
        )

        # 4. スコアリング実行（しきい値 0.40 などで明確に分離できるか確認）
        # paraphrase-multilingual-MiniLM-L12-v2 では関連高いものは通常0.6以上、低いものは0.2以下程度
        res = score_articles(db_path=self.test_db, threshold=0.5)

        self.assertEqual(res["processed"], 2)
        self.assertEqual(res["curated"], 1)

        # 5. DB検証
        with get_connection(self.test_db) as conn:
            cur = conn.cursor()
            cur.execute("SELECT guid, similarity_score, is_curated FROM articles ORDER BY id ASC")
            rows = cur.fetchall()

            self.assertEqual(rows[0]["guid"], "article-high-1")
            self.assertTrue(rows[0]["similarity_score"] > 0.5)
            self.assertEqual(rows[0]["is_curated"], 1)

            self.assertEqual(rows[1]["guid"], "article-low-1")
            self.assertTrue(rows[1]["similarity_score"] < 0.5)
            self.assertEqual(rows[1]["is_curated"], 0)

            # フィードのhit_countが1になっていることを確認
            cur.execute("SELECT hit_count FROM feeds WHERE id = ?", (feed_id,))
            feed_row = cur.fetchone()
            self.assertEqual(feed_row["hit_count"], 1)


if __name__ == "__main__":
    unittest.main()
