"""Tests of how build.py reads songs.json. Run: python -m unittest discover tests"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build  # noqa: E402

VERSION = "8.0.1"


def songs_document(**overrides) -> bytes:
    document = {"schemaVersion": build.SUPPORTED_SCHEMA_VERSION, "version": VERSION, "songs": []}
    return json.dumps({**document, **overrides}).encode()


class ParseSongsDocumentTest(unittest.TestCase):
    def test_accepts_the_supported_schema_version(self):
        document = build.parse_songs_document(songs_document(), "test")
        self.assertEqual(document["version"], VERSION)

    def test_rejects_another_schema_version(self):
        with self.assertRaisesRegex(SystemExit, "schemaVersion"):
            build.parse_songs_document(songs_document(schemaVersion=build.SUPPORTED_SCHEMA_VERSION + 1), "test")

    def test_rejects_a_missing_schema_version(self):
        with self.assertRaisesRegex(SystemExit, "schemaVersion"):
            build.parse_songs_document(b'{"songs": []}', "test")

    def test_rejects_json_that_is_not_an_object(self):
        with self.assertRaisesRegex(SystemExit, "schemaVersion"):
            build.parse_songs_document(b"[]", "test")

    def test_rejects_text_that_is_not_json(self):
        with self.assertRaisesRegex(SystemExit, "not valid JSON"):
            build.parse_songs_document(b"<html>Not Found</html>", "test")


class LoadSongsDocumentTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(self.directory.rmdir)
        patcher = mock.patch.object(build, "DOWNLOAD_DIR", self.directory)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_reads_a_local_file_without_downloading(self):
        local_file = self.directory / "mine.json"
        local_file.write_bytes(songs_document())
        self.addCleanup(local_file.unlink)
        with mock.patch.object(build, "download") as download:
            document = build.load_songs_document(VERSION, local_file)
        download.assert_not_called()
        self.assertEqual(document["version"], VERSION)

    def test_a_missing_local_file_stops_the_build(self):
        with self.assertRaisesRegex(SystemExit, "does not exist"):
            build.load_songs_document(VERSION, self.directory / "missing.json")

    def test_downloads_the_release_asset_of_the_pinned_version(self):
        saved = self.directory / build.SONGS_JSON_ASSET
        self.addCleanup(saved.unlink)
        with mock.patch.object(build, "download", return_value=songs_document()) as download:
            document = build.load_songs_document(VERSION, None)
        download.assert_called_once_with(
            f"https://github.com/f-hluchnik/zpevnik/releases/download/v{VERSION}/songs.json")
        self.assertEqual(document["version"], VERSION)
        self.assertEqual(saved.read_bytes(), songs_document())


if __name__ == "__main__":
    unittest.main()
