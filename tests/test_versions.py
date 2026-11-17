"""Tests of the songbook versions the build reads and the front page's link to
what changed. Run: python -m unittest discover tests"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build  # noqa: E402


class ReadVersionFileTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "version.txt"

    def test_is_the_version_without_the_line_break(self):
        self.path.write_text("8.47.8\n", encoding="utf-8")
        self.assertEqual(build.read_version_file(self.path, "names a release"), "8.47.8")

    def test_stops_the_build_when_the_file_is_missing(self):
        with self.assertRaises(SystemExit) as stop:
            build.read_version_file(self.path, "names a release")
        self.assertIn("version.txt is missing", str(stop.exception))


class ChangesUrlTest(unittest.TestCase):
    def test_compares_the_release_before_the_song_count_changed_with_this_one(self):
        self.assertEqual(
            build.changes_url("8.47.8", "8.38.46"),
            "https://github.com/f-hluchnik/zpevnik/compare/v8.38.46...v8.47.8",
        )

    def test_is_the_link_of_the_front_page(self):
        home = next(page for page in build.load_pages("8.47.8", "8.38.46") if page["is_home"])
        self.assertIn(f'href="{build.changes_url("8.47.8", "8.38.46")}"', home["content"])


if __name__ == "__main__":
    unittest.main()
