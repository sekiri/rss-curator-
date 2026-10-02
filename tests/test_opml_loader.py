import os
import tempfile
from pathlib import Path
from src.opml_loader import import_opml
from src.db import get_feeds, init_db

def test_opml():
    temp_dir = tempfile.gettempdir()
    test_opml = Path(temp_dir) / 'test_seeds.opml'
    test_db = Path(temp_dir) / 'test_loader.db'

    if test_db.exists():
        os.remove(test_db)

    sample_opml_content = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head>
    <title>Sample Feeds</title>
  </head>
  <body>
    <outline text="Tech">
      <outline text="Example Tech News" title="Example Tech News" type="rss" xmlUrl="https://example.com/tech/rss.xml" htmlUrl="https://example.com/tech" />
      <outline text="AI Research" title="AI Research" type="rss" xmlUrl="https://example.com/ai/feed.xml" htmlUrl="https://example.com/ai" />
    </outline>
  </body>
</opml>"""

    test_opml.write_text(sample_opml_content, encoding='utf-8')

    count = import_opml(opml_path=test_opml, db_path=test_db)
    assert count == 2, f"Expected 2 feeds imported, got {count}"

    feeds = get_feeds(db_path=test_db)
    assert len(feeds) == 2, f"Expected 2 feeds in DB, got {len(feeds)}"
    assert feeds[0]["url"] == "https://example.com/tech/rss.xml"
    assert feeds[0]["title"] == "Example Tech News"
    assert feeds[1]["url"] == "https://example.com/ai/feed.xml"

    print("OPML LOADER VERIFICATION PASSED!")

if __name__ == "__main__":
    test_opml()
