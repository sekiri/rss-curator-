import os
import tempfile
import unittest
from pathlib import Path

from src.db import add_feed, get_feeds, init_db, update_feed_stats
from src.pruner import prune_feeds


class TestPruner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.gettempdir()
        self.test_db = Path(self.temp_dir) / f"test_pruner_{os.getpid()}_{self._testMethodName}.db"
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

    def test_prune_feeds(self):
        # Feed 1: 60件フェッチ、1件ヒット (hit_rate = 1/60 = 0.0166 < 0.02) -> 休眠対象
        f1 = add_feed("https://example.com/low_hit.xml", title="Low Hit Feed", db_path=self.test_db)
        update_feed_stats(f1, fetched_increment=60, hit_increment=1, db_path=self.test_db)

        # Feed 2: 60件フェッチ、3件ヒット (hit_rate = 3/60 = 0.05 >= 0.02) -> active維持
        f2 = add_feed("https://example.com/good_hit.xml", title="Good Hit Feed", db_path=self.test_db)
        update_feed_stats(f2, fetched_increment=60, hit_increment=3, db_path=self.test_db)

        # Feed 3: 10件フェッチ、0件ヒット (fetched < 50) -> まだ母数不足のためactive維持
        f3 = add_feed("https://example.com/new_feed.xml", title="New Feed", db_path=self.test_db)
        update_feed_stats(f3, fetched_increment=10, hit_increment=0, db_path=self.test_db)

        dormant_ids = prune_feeds(db_path=self.test_db, min_fetched=50, min_hit_rate=0.02)

        self.assertEqual(dormant_ids, [f1])

        feeds = {feed["id"]: feed["status"] for feed in get_feeds(db_path=self.test_db)}
        self.assertEqual(feeds[f1], "dormant")
        self.assertEqual(feeds[f2], "active")
        self.assertEqual(feeds[f3], "active")


if __name__ == "__main__":
    unittest.main()
