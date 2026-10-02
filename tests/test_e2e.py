import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import feedparser

from src.main import run_pipeline


class TestE2EPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.gettempdir()
        pid = os.getpid()
        self.test_db = Path(self.temp_dir) / f"test_e2e_{pid}.db"
        self.test_bms = Path(self.temp_dir) / f"test_e2e_bms_{pid}.txt"
        self.test_opml = Path(self.temp_dir) / f"test_e2e_seeds_{pid}.opml"
        self.test_out_xml = Path(self.temp_dir) / f"test_e2e_curated_{pid}.xml"

        for p in [self.test_db, self.test_bms, self.test_opml, self.test_out_xml]:
            if p.exists():
                try:
                    os.remove(p)
                except OSError:
                    pass

    def tearDown(self):
        for p in [self.test_db, self.test_bms, self.test_opml, self.test_out_xml]:
            if p.exists():
                try:
                    os.remove(p)
                except OSError:
                    pass

    def test_full_pipeline(self):
        # 1. OPMLファイルの準備
        opml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <opml version="2.0">
          <head><title>E2E Feeds</title></head>
          <body>
            <outline text="AI Feed" title="AI News" type="rss" xmlUrl="https://example.com/ai.xml" htmlUrl="https://example.com" />
          </body>
        </opml>"""
        self.test_opml.write_text(opml_content, encoding="utf-8")

        # 2. ブックマークファイルの準備（Python, AI, LLM）
        bms_content = """# User bookmarks
Python programming and software architecture
Generative AI, Large Language Models and agents
"""
        self.test_bms.write_text(bms_content, encoding="utf-8")

        # 3. フィードのレスポンスXML準備（高関連1件、低関連1件）
        feed_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>AI News</title>
            <link>https://example.com</link>
            <description>News about AI</description>
            <item>
              <title>State of Autonomous LLM Agents in Python</title>
              <link>https://example.com/item-ai</link>
              <guid>guid-e2e-ai-1</guid>
              <description>Comprehensive overview of LLM agents built with Python libraries.</description>
              <pubDate>Wed, 30 Sep 2026 12:00:00 GMT</pubDate>
            </item>
            <item>
              <title>Beginners guide to gardening and planting indoor flowers</title>
              <link>https://example.com/item-garden</link>
              <guid>guid-e2e-garden-1</guid>
              <description>Learn how to water and pot house plants for spring.</description>
              <pubDate>Wed, 30 Sep 2026 11:00:00 GMT</pubDate>
            </item>
          </channel>
        </rss>
        """

        mock_resp = MagicMock()
        mock_resp.content = feed_xml
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_resp):
            # パイプライン実行（閾値 0.5）
            run_pipeline(
                db_path=self.test_db,
                bookmarks_path=self.test_bms,
                opml_path=self.test_opml,
                output_path=self.test_out_xml,
                threshold=0.5,
            )

        # 4. 生成された XML の検証
        self.assertTrue(self.test_out_xml.exists(), "curated.xml must be generated")

        parsed = feedparser.parse(str(self.test_out_xml))
        self.assertEqual(len(parsed.entries), 1, "Only the relevant article should be curated")
        self.assertEqual(parsed.entries[0].title, "State of Autonomous LLM Agents in Python")
        self.assertEqual(parsed.entries[0].link, "https://example.com/item-ai")
        print("E2E PIPELINE TEST PASSED!")


if __name__ == "__main__":
    unittest.main()
