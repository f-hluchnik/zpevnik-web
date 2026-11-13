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


def song(song_id, body=(), see=(), artists=(), collections=()):
    return {
        "id": song_id,
        "body": list(body),
        "see": [{"id": target, "title": []} for target in see],
        "artists": [{"slug": slug, "label": label} for slug, label in artists],
        "collections": list(collections),
    }


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


class ArtistReferencesTest(unittest.TestCase):
    def test_lists_the_artists_and_then_the_collections(self):
        with_both = song("a", artists=[("abba", None), ("queen", "Q.")], collections=["filmy"])
        self.assertEqual(
            songbook.artist_references(with_both),
            [("abba", None), ("queen", "Q."), ("filmy", None)],
        )

    def test_a_song_of_nobody_has_none(self):
        self.assertEqual(songbook.artist_references(song("a")), [])


class BookNeighboursTest(unittest.TestCase):
    def test_pairs_each_song_with_the_ones_around_it(self):
        a, b, c = song("a"), song("b"), song("c")
        self.assertEqual(
            list(songbook.book_neighbours([a, b, c])),
            [(None, a, b), (a, b, c), (b, c, None)],
        )

    def test_a_single_song_has_no_neighbours(self):
        a = song("a")
        self.assertEqual(list(songbook.book_neighbours([a])), [(None, a, None)])

    def test_no_songs_no_pairs(self):
        self.assertEqual(list(songbook.book_neighbours([])), [])


class CheckFreeIdsTest(unittest.TestCase):
    def test_accepts_ids_that_clash_with_nothing(self):
        songbook.check_free_ids([song("a"), song("b")], reserved=["interpret"])

    def test_stops_at_an_id_that_a_page_of_the_songbook_has(self):
        with self.assertRaisesRegex(SystemExit, "'interpret'"):
            songbook.check_free_ids([song("a"), song("interpret")], reserved=["interpret"])


def run(text):
    return {"type": "run", "text": text, "style": []}


GAP = {"type": "gap", "em": 1}
FOOTNOTE = {"type": "footnote", "number": 1}


class PlainTextTest(unittest.TestCase):
    def test_joins_the_runs(self):
        self.assertEqual(songbook.plain_text([run("Ain’t "), run("no grave")]), "Ain’t no grave")

    def test_a_pause_is_a_space_and_a_footnote_mark_is_nothing(self):
        self.assertEqual(songbook.plain_text([run("one"), GAP, run("two"), FOOTNOTE, run("!")]), "one two!")

    def test_a_run_of_spaces_is_one(self):
        self.assertEqual(songbook.plain_text([run(" a  b\u00a0 c ")]), "a b c")


class LyricsLinesTest(unittest.TestCase):
    def lyrics_segment(self, chord, *parts):
        return {"type": "segment", "chord": chord, "lyrics": list(parts), "endsInWord": False}

    def test_a_word_split_by_a_chord_is_whole_again(self):
        first = line(self.lyrics_segment(CHORD, run("to")), self.lyrics_segment(CHORD, run("mu je ")))
        self.assertEqual(songbook.lyrics_lines(song("a", [{"type": "block", "lines": [first]}])), ["tomu je"])

    def test_takes_the_lines_of_every_block_and_leaves_out_what_is_not_lyrics(self):
        words = line(self.lyrics_segment(None, run("la")), {"type": "cue", "label": "Refrén"}, SCORE)
        chords_only = line(self.lyrics_segment(CHORD))
        body = [
            {"type": "block", "lines": [words, chords_only]},
            {"type": "cueBlock", "line": line(self.lyrics_segment(None, run("lo")))},
            {"type": "note", "content": [run("not lyrics")]},
        ]
        self.assertEqual(songbook.lyrics_lines(song("a", body)), ["la", "lo"])


class SearchEntryTest(unittest.TestCase):
    def test_holds_the_titles_the_artists_and_the_lyrics(self):
        artists = {"abba": {"linkLabel": "ABBA"}, "filmy": {"linkLabel": "filmová hudba"}}
        the_song = {
            **song("dance", [{"type": "block", "lines": [line(segment(None, "Hej"))]}],
                   artists=[("abba", None)], collections=["filmy"]),
            "tocTitle": "Dance", "altTitles": ["Tanec"],
        }
        self.assertEqual(songbook.search_entry(the_song, artists), {
            "id": "dance", "title": "Dance", "altTitles": ["Tanec"],
            "artists": ["ABBA", "filmová hudba"], "lyrics": "Hej",
        })

    def test_the_song_s_own_wording_of_an_artist_is_what_is_searched(self):
        the_song = {**song("a", artists=[("lenk", "J. S. Lenk")]), "tocTitle": "A", "altTitles": []}
        entry = songbook.search_entry(the_song, {"lenk": {"linkLabel": "Jaroslav Samson Lenk"}})
        self.assertEqual(entry["artists"], ["J. S. Lenk"])


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


def chord_segment(chord, *parts):
    return {"type": "segment", "chord": chord, "lyrics": list(parts), "endsInWord": False}


E7 = [{"text": "E", "position": "base"}, {"text": "7", "position": "superscript"}]  # covered by 5 characters


class ChordHeadLengthTest(unittest.TestCase):
    def test_counts_every_part_of_the_chord_as_wider_letters_and_adds_the_separator(self):
        self.assertEqual(songbook.chord_head_length(CHORD), 4)  # ceil(1 × 1.3) + 2
        self.assertEqual(songbook.chord_head_length(E7), 5)  # ceil(2 × 1.3) + 2


class SplitHeadTest(unittest.TestCase):
    def test_the_head_is_the_shortest_run_of_whole_words_that_covers_the_chord(self):
        head, tail = songbook.split_head(chord_segment(E7, run("I don’t know when.")))
        self.assertEqual((head, tail), ([run("I don’t")], [run(" know when.")]))

    def test_a_text_that_does_not_reach_past_the_chord_is_all_head(self):
        segment = chord_segment(E7, run("I don’t "))
        self.assertEqual(songbook.split_head(segment), (segment["lyrics"], []))

    def test_a_text_without_spaces_is_all_head(self):
        segment = chord_segment(CHORD, run("Antone."))
        self.assertEqual(songbook.split_head(segment), (segment["lyrics"], []))

    def test_the_tail_starts_with_the_space_and_keeps_the_style(self):
        italic = {"type": "run", "text": "seven two", "style": ["italic"]}
        head, tail = songbook.split_head(chord_segment(CHORD, italic))
        self.assertEqual(head, [{**italic, "text": "seven"}])
        self.assertEqual(tail, [{**italic, "text": " two"}])

    def test_the_cut_may_fall_between_runs_and_takes_the_later_parts_along(self):
        head, tail = songbook.split_head(chord_segment(CHORD, run("I"), run("t is"), run(" so "), FOOTNOTE, run("now")))
        self.assertEqual(head, [run("I"), run("t is")])
        self.assertEqual(tail, [run(" so "), FOOTNOTE, run("now")])

    def test_a_pause_counts_by_its_length_and_a_footnote_mark_not_at_all(self):
        head, _ = songbook.split_head(chord_segment(CHORD, GAP, run("ab c")))  # the pause is 2 characters
        self.assertEqual(head, [GAP, run("ab")])
        head, _ = songbook.split_head(chord_segment(CHORD, FOOTNOTE, run("ab cd e")))
        self.assertEqual(head, [FOOTNOTE, run("ab cd")])

    def test_a_tail_without_a_word_is_no_tail(self):
        segment = chord_segment(CHORD, run("one "), GAP, FOOTNOTE)
        self.assertEqual(songbook.split_head(segment), (segment["lyrics"], []))

    def test_a_text_without_a_chord_is_all_head(self):
        segment = chord_segment(None, run("but that train keeps a-rollin’"))
        self.assertEqual(songbook.split_head(segment), (segment["lyrics"], []))


def in_word(item):
    return {**item, "endsInWord": True}


class WordGroupsTest(unittest.TestCase):
    def test_a_column_that_ends_inside_a_word_is_grouped_with_the_next_segment(self):
        fee, lin, blue = in_word(chord_segment(CHORD, run("fee"))), chord_segment(CHORD, run("lin’ ")), chord_segment(CHORD, run("blue"))
        self.assertEqual(songbook.word_groups([fee, lin, blue]), [[fee, lin], [blue]])

    def test_a_word_split_by_three_chords_is_one_group(self):
        ko, lo, toc = in_word(chord_segment(CHORD, run("ko"))), in_word(chord_segment(CHORD, run("lo"))), chord_segment(CHORD, run("toč"))
        self.assertEqual(songbook.word_groups([ko, lo, toc]), [[ko, lo, toc]])

    def test_text_that_flows_is_not_grouped(self):
        with_tail = in_word(chord_segment(CHORD, run("seven klo")))  # the tail " klo" flows, with a soft hyphen
        without_chord = in_word(chord_segment(None, run("Buongiorno I")))
        bouk = chord_segment(CHORD, run("bouk"))
        self.assertEqual(songbook.word_groups([with_tail, bouk]), [[with_tail], [bouk]])
        self.assertEqual(songbook.word_groups([without_chord, bouk]), [[without_chord], [bouk]])

    def test_only_a_segment_with_a_chord_joins_a_group(self):
        fee = in_word(chord_segment(CHORD, run("fee")))
        self.assertEqual(songbook.word_groups([fee, SCORE]), [[fee], [SCORE]])


if __name__ == "__main__":
    unittest.main()
