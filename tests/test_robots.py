"""Test of robots.txt (W6). Run: python -m unittest discover tests"""

import sys
import unittest
from pathlib import Path
from urllib.robotparser import RobotFileParser

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build  # noqa: E402

CRAWLERS = ("Googlebot", "bingbot", "SomeOtherBot")
PATHS = (
    "/",
    "/zpivej/",
    "/zpivej/hledat/",
    "/zpivej/folsomprisonblues/",
    build.SONGBOOK_PDF_URL,
    build.SEARCH_INDEX_URL_PATH,
)


class RobotsTxtTest(unittest.TestCase):
    def setUp(self):
        self.parser = RobotFileParser()
        self.parser.parse(build.ROBOTS_TXT.splitlines())

    def test_no_crawler_may_read_any_page_or_file(self):
        for crawler in CRAWLERS:
            for path in PATHS:
                with self.subTest(crawler=crawler, path=path):
                    self.assertFalse(self.parser.can_fetch(crawler, path))

    def test_there_is_no_sitemap(self):
        self.assertIsNone(self.parser.site_maps())


if __name__ == "__main__":
    unittest.main()
