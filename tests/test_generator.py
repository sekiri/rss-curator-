import os
import tempfile
import unittest
from pathlib import Path

import feedparser

from src.db import add_feed, init_db, insert_article, update_article_score
from src.generator import generate_rss_feed


class TestGenerator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.gettempdir()
        self.test_db = Path(self.temp_dir) / f"test_gen_{os.getpid()}_{self._testMethodName}.db"
        self.output_xml = Path(self.temp_dir) / f"curated_{os.getpid()}_{self._testMethodName}.xml"
        if self.test_db.exists():
            try:
                os.remove(self.test_db)
            except OSError:
                pass
        init_db(self.test_db)

    def tearDown(self):
        for p in [self.test_db, self.output_xml]:
            if p.exists():
                try:
                    os.remove(p)
                except OSError:
                    pass

    def test_generate_rss_feed(self):
        feed_id = add_feed("https://example.com/feed.xml", title="Tech Feed", db_path=self.test_db)

        # 記事1: 採用（is_curated=1）
        insert_article(
            feed_id=feed_id,
            guid="item-1",
            title="Exciting AI Discovery",
            link="https://example.com/item-1",
            published_at="2026-09-30T12:00:00",
            content_snippet="Breakthrough in LLM reasoning.",
            db_path=self.test_db,
        )
        update_article_score(article_id=1, score=0.88, is_curated=True, db_path=self.test_db)

        # 記事2: 非採用（is_curated=0）
        insert_article(
            feed_id=feed_id,
            guid="item-2",
            title="Irrelevant Gossip",
            link="https://example.com/item-2",
            published_at="2026-09-30T13:00:00",
            content_snippet="Celebrity news of the day.",
            db_path=self.test_db,
        )
        update_article_score(article_id=2, score=0.15, is_curated=False, db_path=self.test_db)

        # RSSフィード生成
        generated_file = generate_rss_feed(
            db_path=self.test_db,
            output_path=self.output_xml,
            feed_title="My Curated Feed",
            feed_link="https://example.com/curated.xml",
        )

        self.assertTrue(generated_file.exists())

        # feedparser で生成された XML のパースと検証
        parsed = feedparser.parse(str(generated_file))
        self.assertEqual(parsed.feed.title, "My Curated Feed")
        self.assertEqual(len(parsed.entries), 1)
        self.assertEqual(parsed.entries[0].title, "Exciting AI Discovery")
        self.assertEqual(parsed.entries[0].link, "https://example.com/item-1")
        self.assertIn("0.88", parsed.entries[0].description)


if __name__ == "__main__":
    unittest.main()
