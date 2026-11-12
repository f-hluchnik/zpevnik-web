"""Tests of the check of the built site (W7). Run: python -m unittest discover tests"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check_site  # noqa: E402


def page(body: str) -> str:
    return f"<!doctype html><html><head></head><body>{body}</body></html>"


class SiteTestCase(unittest.TestCase):
    """A small site in a temporary directory."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.site = Path(directory.name)

    def write(self, relative_path: str, content: str = "") -> None:
        path = self.site / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


class ReadPageTest(unittest.TestCase):
    def test_finds_the_references_and_the_anchors(self):
        reader = check_site.read_page(
            '<a href="/a/">x</a><script src="/s.js"></script><link rel="stylesheet" href="/c.css">'
            '<form action="/f/"></form><img src="/i.png"><p id="here"></p><a name="there"></a><a>no href</a>'
        )
        self.assertEqual(reader.references, ["/a/", "/s.js", "/c.css", "/f/", "/i.png"])
        self.assertEqual(reader.anchors, {"here", "there"})


class IsInternalTest(unittest.TestCase):
    def test_only_a_reference_without_scheme_and_host_is_of_the_site(self):
        for reference in ("/a/", "b/", "#x", "?q=1", "../c.html"):
            self.assertTrue(check_site.is_internal(reference), reference)
        for reference in ("https://example.org/", "//example.org/a", "mailto:a@b.cz", "tel:123"):
            self.assertFalse(check_site.is_internal(reference), reference)


class LinkProblemsTest(SiteTestCase):
    def test_a_site_whose_links_all_lead_somewhere_has_no_problem(self):
        self.write("index.html", page('<a href="/songs/">s</a><a href="/songs/one/">one</a><a href="/f.pdf#page=3">pdf</a>'
                                      '<a href="https://example.org/missing">out</a>'))
        self.write("songs/index.html", page('<a href="one/">one</a><a href="#top" id="top">up</a>'))
        self.write("songs/one/index.html", page(""))
        self.write("f.pdf")
        self.assertEqual(check_site.link_problems(self.site), [])

    def test_a_missing_page_or_file_is_reported_with_the_page_that_links_to_it(self):
        self.write("index.html", page('<a href="/songs/gone/">x</a><script src="/static/gone.js"></script>'))
        self.assertEqual(
            check_site.link_problems(self.site),
            ["/: /songs/gone/ leads nowhere", "/: /static/gone.js leads nowhere"],
        )

    def test_a_query_string_is_not_part_of_the_file_name(self):
        self.write("index.html", page('<script src="/static/a.js?v=0123abcd"></script>'))
        self.write("static/a.js")
        self.assertEqual(check_site.link_problems(self.site), [])

    def test_a_relative_link_is_resolved_from_the_page_it_stands_on(self):
        self.write("a/b/index.html", page('<a href="../c/">c</a><a href="../missing/">m</a>'))
        self.write("a/c/index.html", page(""))
        self.assertEqual(check_site.link_problems(self.site), ["/a/b/: ../missing/ leads nowhere"])

    def test_an_anchor_must_exist_on_its_page_or_on_the_page_linked_to(self):
        self.write("index.html", page('<a href="#nowhere">n</a><a href="/other/#fn1">ok</a><a href="/other/#fn9">bad</a>'))
        self.write("other/index.html", page('<li id="fn1"></li>'))
        self.assertEqual(
            check_site.link_problems(self.site),
            ["/: #nowhere has no anchor #nowhere", "/: /other/#fn9 has no anchor #fn9"],
        )


class MissingSongPagesTest(SiteTestCase):
    def test_a_song_without_a_page_is_reported(self):
        self.write("zpivej/one/index.html", page(""))
        self.assertEqual(
            check_site.missing_song_pages(self.site, ["one", "two"], "/zpivej/"),
            ["song two has no page"],
        )


if __name__ == "__main__":
    unittest.main()
