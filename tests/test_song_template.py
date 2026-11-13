"""Tests of the HTML of a line of a song (templates/_song.html), drawn from the
pieces of songbook.layout_line. Run: python -m unittest discover tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build  # noqa: E402

CHORD = [{"text": "C", "position": "base"}]


def run(text):
    return {"type": "run", "text": text, "style": []}


def segment(chord, text, ends_in_word=False):
    return {"type": "segment", "chord": chord, "lyrics": [run(text)], "endsInWord": ends_in_word}


def render_line(*items):
    template = build.env.get_template("_song.html")
    return str(template.module.line({"groupStart": False, "items": list(items)}))


def render_body_item(item):
    template = build.env.get_template("_song.html")
    return str(template.module.body_item(item))


class RemarkHtmlTest(unittest.TestCase):
    def test_a_remark_is_a_paragraph_with_a_line_break_between_its_lines(self):
        italic = {"type": "run", "text": "D", "style": ["italic"]}
        remark = {"type": "remark", "lines": [[run("4/4 | 3/4")], [run("G "), italic]]}
        self.assertEqual(
            render_body_item(remark),
            '<p class="song-remark">4/4 | 3/4<br>G <span class="run-italic">D</span></p>')

    def test_a_remark_of_one_line_has_no_line_break(self):
        self.assertEqual(render_body_item({"type": "remark", "lines": [[run("interludium")]]}),
                         '<p class="song-remark">interludium</p>')


class LineHtmlTest(unittest.TestCase):
    def test_a_column_and_its_tail_with_no_space_between_the_elements(self):
        self.assertEqual(
            render_line(segment(CHORD, "seven two")),
            '<div class="line"><span class="segment"><span class="chord">C</span>'
            '<span class="lyrics">seven</span></span><span class="flow"> two</span></div>')

    def test_text_that_flows_into_a_word_ends_in_a_soft_hyphen(self):
        self.assertEqual(
            render_line(segment(None, "Buongiorno I", ends_in_word=True), segment(CHORD, "talia")),
            '<div class="line"><span class="flow">Buongiorno I&shy;</span><span class="segment">'
            '<span class="chord">C</span><span class="lyrics">talia</span></span></div>')

    def test_columns_that_share_a_word_are_one_group_and_the_gap_may_hold_a_hyphen(self):
        self.assertEqual(
            render_line(segment(CHORD, "fee", ends_in_word=True), segment(CHORD, "lin’ blue")),
            '<div class="line"><span class="word"><span class="segment"><span class="chord">C</span>'
            '<span class="lyrics"><span class="lyrics-text">fee</span><span class="hyphen-room">'
            '<span class="hyphen"></span></span></span></span><span class="segment"><span class="chord">C</span>'
            '<span class="lyrics">lin’</span></span></span><span class="flow"> blue</span></div>')


if __name__ == "__main__":
    unittest.main()
