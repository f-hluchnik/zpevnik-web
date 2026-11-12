"""Tests of songbook.py. Run: python -m unittest discover tests"""

import io
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import songbook  # noqa: E402


def segment(chord, lyrics):
    runs = [{"type": "run", "text": lyrics, "style": []}] if lyrics else []
    return {"type": "segment", "chord": chord, "lyrics": runs, "endsInWord": False}


def line(*items):
    return {"groupStart": False, "items": list(items)}


def song(song_id, body, see=()):
    return {"id": song_id, "body": body, "see": [{"id": target, "title": []} for target in see]}


def zip_with(*names):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, "<svg/>")
    return buffer.getvalue()


CHORD = [{"text": "C", "position": "base"}]
SCORE = {"type": "score", "name": "riff"}


class BodyLinesTest(unittest.TestCase):
    def test_finds_the_lines_of_every_kind_of_block(self):
        lines = [line(segment(None, str(n))) for n in range(4)]
        body = [
            {"type": "block", "lines": lines[0:2]},
            {"type": "speakerBlock", "lines": lines[2:3]},
            {"type": "cueBlock", "line": lines[3]},
            {"type": "note"},
            {"type": "rule"},
        ]
        self.assertEqual(list(songbook.body_lines(song("a", body))), lines)


class ScoreNamesTest(unittest.TestCase):
    def test_collects_the_scores_of_all_songs(self):
        with_score = song("a", [{"type": "block", "lines": [line(SCORE)]}])
        other_score = song("b", [{"type": "cueBlock", "line": line({**SCORE, "name": "tune"})}])
        without = song("c", [{"type": "block", "lines": [line(segment(CHORD, "text"))]}])
        self.assertEqual(songbook.score_names([with_score, other_score, without]), {"riff", "tune"})


class ChordOnlyLineTest(unittest.TestCase):
    def test_chords_without_words_are_a_chord_only_line(self):
        self.assertTrue(songbook.is_chord_only_line(line(segment(CHORD, ""), segment(CHORD, ""))))

    def test_a_line_with_words_is_not(self):
        self.assertFalse(songbook.is_chord_only_line(line(segment(CHORD, ""), segment(CHORD, "la"))))

    def test_words_without_chords_are_not(self):
        self.assertFalse(songbook.is_chord_only_line(line(segment(None, "la"))))

    def test_a_line_of_something_else_is_not(self):
        self.assertFalse(songbook.is_chord_only_line(line(SCORE)))


class CheckSeeLinksTest(unittest.TestCase):
    def test_accepts_a_link_to_a_song_of_the_book(self):
        songbook.check_see_links([song("a", [], see=["b"]), song("b", [])])

    def test_stops_at_a_link_to_an_unknown_song(self):
        with self.assertRaisesRegex(SystemExit, "'a'.*'unknown'"):
            songbook.check_see_links([song("a", [], see=["unknown"])])


class ScoreImagesTest(unittest.TestCase):
    def test_reads_the_svg_files(self):
        images = songbook.read_score_images(zip_with("riff.svg", "tune.svg"), "test")
        self.assertEqual(images, {"riff.svg": b"<svg/>", "tune.svg": b"<svg/>"})

    def test_ignores_what_is_not_a_plain_svg_name(self):
        images = songbook.read_score_images(
            zip_with("riff.svg", "riff.pdf", "../escape.svg", "folder/tune.svg"), "test")
        self.assertEqual(set(images), {"riff.svg"})

    def test_stops_at_something_that_is_not_a_zip(self):
        with self.assertRaisesRegex(SystemExit, "not a zip"):
            songbook.read_score_images(b"<html>Not Found</html>", "test")

    def test_stops_when_a_shown_score_is_missing(self):
        songs = [song("a", [{"type": "block", "lines": [line(SCORE)]}])]
        songbook.check_scores_present(songs, {"riff.svg": b""})
        with self.assertRaisesRegex(SystemExit, "riff"):
            songbook.check_scores_present(songs, {})


if __name__ == "__main__":
    unittest.main()
