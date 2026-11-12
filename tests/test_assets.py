"""Tests of the versioned URLs of the style sheets and scripts. Run: python -m unittest discover tests"""

import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build  # noqa: E402


class ContentVersionTest(unittest.TestCase):
    def test_is_short_and_made_of_hex_digits(self):
        self.assertRegex(build.content_version(b"body { color: red }"), rf"^[0-9a-f]{{{build.CONTENT_VERSION_LENGTH}}}$")

    def test_the_same_content_has_the_same_version_and_other_content_another(self):
        self.assertEqual(build.content_version(b"a"), build.content_version(b"a"))
        self.assertNotEqual(build.content_version(b"a"), build.content_version(b"b"))


class AssetUrlTest(unittest.TestCase):
    def setUp(self):
        self.static = tempfile.TemporaryDirectory()
        self.addCleanup(self.static.cleanup)
        patcher = mock.patch.object(build, "STATIC_DIR", Path(self.static.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, name, content):
        (Path(self.static.name) / name).write_bytes(content)

    def test_names_the_file_and_the_version_of_its_content(self):
        self.write("site.css", b"a")
        self.assertEqual(build.asset_url("site.css"), f"/static/site.css?v={build.content_version(b'a')}")

    def test_the_url_changes_when_the_file_does(self):
        self.write("site.css", b"a")
        before = build.asset_url("site.css")
        self.write("site.css", b"b")
        self.assertNotEqual(build.asset_url("site.css"), before)

    def test_stops_at_a_file_that_does_not_exist(self):
        with self.assertRaises(FileNotFoundError):
            build.asset_url("missing.css")


class SearchIndexTest(unittest.TestCase):
    def test_is_compact_utf8_json_in_book_order(self):
        document = {
            "artists": [],
            "songs": [
                {"id": "b", "tocTitle": "Čerešně", "altTitles": [], "artists": [], "collections": [], "body": []},
                {"id": "a", "tocTitle": "A", "altTitles": [], "artists": [], "collections": [], "body": []},
            ],
        }
        raw = build.search_index_json(document).decode("utf-8")
        self.assertIn("Čerešně", raw)  # not escaped
        self.assertNotRegex(raw, r"\s")  # compact: no spaces, no newlines
        self.assertEqual([m for m in re.findall(r'"id":"(\w)"', raw)], ["b", "a"])


if __name__ == "__main__":
    unittest.main()
