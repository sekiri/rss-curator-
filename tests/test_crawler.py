import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.crawler import clean_html, crawl_all, extract_content_snippet, fetch_feed, parse_published_date
from src.db import add_feed, get_connection, get_feeds, init_db, update_feed_status


class TestCrawler(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.gettempdir()
        self.test_db = Path(self.temp_dir) / f"test_crawler_{os.getpid()}_{self._testMethodName}.db"
        if self.test_db.exists():
            try:
                os.remove(self.test_db)
            except OSError:
                pass
        init_db(self.test_db)

    def tearDown(self):
        if self.test_db.exists():
            try:
                os.remove(self.test_db)
            except OSError:
                pass

    def test_clean_html(self):
        html_input = "<p>Hello <b>World</b>!</p><script>alert('xss');</script>&amp; Welcome"
        expected = "Hello World ! & Welcome"
        self.assertEqual(clean_html(html_input), expected)

    def test_parse_published_date(self):
        entry = {"published": "Wed, 30 Sep 2026 12:00:00 GMT"}
        parsed = parse_published_date(entry)
        self.assertTrue(parsed.startswith("2026-09-30"))

    def test_fetch_feed_and_duplicate_prevention(self):
        feed_id = add_feed("https://example.com/rss.xml", title="Example Feed", db_path=self.test_db)

        sample_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>Example Feed</title>
            <link>https://example.com</link>
            <description>Example News</description>
            <item>
              <title>Article 1</title>
              <link>https://example.com/1</link>
              <guid>https://example.com/1</guid>
              <description><![CDATA[Summary 1 with <p>HTML</p>]]></description>
              <pubDate>Wed, 30 Sep 2026 10:00:00 GMT</pubDate>
            </item>
            <item>
              <title>Article 2</title>
              <link>https://example.com/2</link>
              <guid>https://example.com/2</guid>
              <description>Summary 2</description>
              <pubDate>Wed, 30 Sep 2026 11:00:00 GMT</pubDate>
            </item>
          </channel>
        </rss>
        """

        mock_resp = MagicMock()
        mock_resp.content = sample_xml
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            # 初回フェッチ: 2件挿入されるはず
            count1 = fetch_feed(feed_id=feed_id, feed_url="https://example.com/rss.xml", db_path=self.test_db)
            self.assertEqual(count1, 2)

            # フィードの total_fetched 確認
            feeds = get_feeds(db_path=self.test_db)
            self.assertEqual(feeds[0]["total_fetched"], 2)

            # 2回目フェッチ（同一内容）: 重複のため0件挿入
            count2 = fetch_feed(feed_id=feed_id, feed_url="https://example.com/rss.xml", db_path=self.test_db)
            self.assertEqual(count2, 0)

            # DB内の記事総数は2件のまま
            with get_connection(self.test_db) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM articles")
                self.assertEqual(cur.fetchone()[0], 2)

    def test_crawl_all(self):
        f1 = add_feed("https://example.com/active.xml", title="Active Feed", db_path=self.test_db)
        f2 = add_feed("https://example.com/dormant.xml", title="Dormant Feed", db_path=self.test_db)
        update_feed_status(f2, "dormant", db_path=self.test_db)

        with patch("src.crawler.fetch_feed", return_value=3) as mock_fetch:
            res = crawl_all(db_path=self.test_db, dormant_fetch_rate=0.0)
            self.assertEqual(res["feeds_processed"], 1)
            self.assertEqual(res["new_articles"], 3)
            mock_fetch.assert_called_once_with(
                feed_id=f1,
                feed_url="https://example.com/active.xml",
                db_path=self.test_db,
            )


if __name__ == "__main__":
    unittest.main()
