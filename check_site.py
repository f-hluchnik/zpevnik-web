"""The release check of the built site (W7): run it after build.py.

    python check_site.py [DIST_DIR] [--songs-json FILE]

It fails (exit status 1, the problems listed) when
  - a song of songs.json has no page,
  - a link, script, style sheet, image or form action of any page points to a
    file the site does not have, or to an anchor (#id) its page does not have,
  - a chord has a character that neither chord font draws (it would be taken
    from the reader's system).
Only the site itself is checked: addresses with a scheme (https:, mailto:) and
the fonts and files the style sheets name are not.
"""

from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urldefrag, urljoin, urlsplit

import build
import songbook

INDEX_FILE_NAME = "index.html"
# The attribute of a tag that names another file of the site.
REFERENCE_ATTRIBUTES = {"a": "href", "link": "href", "script": "src", "img": "src", "form": "action"}
PROBLEMS_SHOWN = 20

# The chord fonts (static/fonts/README.md). The letter font draws ASCII and the
# ellipsis; every other character of a chord must be in the unicode-range of a
# symbols face in songbook.css (only those faces have a unicode-range).
CHORD_LETTER_FONT_EXTRA_CHARACTERS = {"\u2026"}
UNICODE_RANGE = re.compile(r"unicode-range:\s*([^;]+);")
UNICODE_RANGE_ENTRY = re.compile(r"U\+([0-9A-Fa-f]+)(?:-([0-9A-Fa-f]+))?")


class PageReader(HTMLParser):
    """The references of a page and the anchors it offers."""

    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []
        self.anchors: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        for name in ("id", "name"):
            if attributes.get(name):
                self.anchors.add(attributes[name])
        reference = attributes.get(REFERENCE_ATTRIBUTES.get(tag, ""))
        if reference:
            self.references.append(reference)


def read_page(html: str) -> PageReader:
    reader = PageReader()
    reader.feed(html)
    return reader


def is_internal(reference: str) -> bool:
    """A reference to a file of this site: no scheme, no host."""
    parts = urlsplit(reference)
    return not parts.scheme and not parts.netloc


def file_of(site_dir: Path, url_path: str) -> Path | None:
    """The file a server would answer with for this path, if there is one."""
    target = site_dir / unquote(url_path).lstrip("/")
    if target.is_dir():
        target = target / INDEX_FILE_NAME
    return target if target.is_file() else None


def url_of(site_dir: Path, page: Path) -> str:
    """The address of a page file: dist/zpivej/x/index.html is /zpivej/x/."""
    url = "/" + page.relative_to(site_dir).as_posix()
    return url.removesuffix(INDEX_FILE_NAME)


def link_problems(site_dir: Path) -> list[str]:
    readers: dict[Path, PageReader] = {}

    def reader_of(page: Path) -> PageReader:
        if page not in readers:
            readers[page] = read_page(page.read_text(encoding="utf-8"))
        return readers[page]

    problems = []
    for page in sorted(site_dir.rglob("*.html")):
        page_url = url_of(site_dir, page)
        for reference in reader_of(page).references:
            if not is_internal(reference):
                continue
            target_url, anchor = urldefrag(urljoin(page_url, reference))
            target = file_of(site_dir, urlsplit(target_url).path) if target_url else page
            if target is None:
                problems.append(f"{page_url}: {reference} leads nowhere")
            elif anchor and target.suffix == ".html" and anchor not in reader_of(target).anchors:
                problems.append(f"{page_url}: {reference} has no anchor #{anchor}")
    return problems


def missing_song_pages(site_dir: Path, song_ids: list[str], songbook_path: str) -> list[str]:
    return [
        f"song {song_id} has no page"
        for song_id in song_ids
        if file_of(site_dir, f"{songbook_path}{song_id}/") is None
    ]


def chord_symbols_in_css(css: str) -> set[str]:
    """The characters the style sheet gives to the symbol faces (their unicode-ranges)."""
    return {
        chr(code)
        for ranges in UNICODE_RANGE.findall(css)
        for first, last in UNICODE_RANGE_ENTRY.findall(ranges)
        for code in range(int(first, 16), int(last or first, 16) + 1)
    }


def unfonted_chord_characters(songs: list[dict], css: str) -> list[str]:
    """The problems of chord characters no chord font draws."""
    drawn = chord_symbols_in_css(css) | CHORD_LETTER_FONT_EXTRA_CHARACTERS
    return [
        f"chord character {character!r} (U+{ord(character):04X}) is in no chord font"
        for character in sorted(songbook.chord_characters(songs))
        if ord(character) > 127 and character not in drawn
    ]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check the built site: every song has a page, every link leads somewhere.")
    parser.add_argument("site_dir", nargs="?", type=Path, default=build.OUTPUT_DIR, help="the built site (default: dist/)")
    parser.add_argument("--songs-json", type=Path, default=build.DOWNLOAD_DIR / build.SONGS_JSON_ASSET, metavar="FILE",
                        help="the songs.json the site was built from (default: the one build.py downloaded)")
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    document = build.parse_songs_document(arguments.songs_json.read_bytes(), str(arguments.songs_json))
    song_ids = [song["id"] for song in document["songs"]]
    songbook_css = (arguments.site_dir / "static" / "songbook.css").read_text(encoding="utf-8")
    problems = (missing_song_pages(arguments.site_dir, song_ids, build.SONGBOOK_URL_PATH)
                + link_problems(arguments.site_dir)
                + unfonted_chord_characters(document["songs"], songbook_css))
    for problem in problems[:PROBLEMS_SHOWN]:
        print(problem)
    if len(problems) > PROBLEMS_SHOWN:
        print(f"… and {len(problems) - PROBLEMS_SHOWN} more")
    pages = len(list(arguments.site_dir.rglob("*.html")))
    print(f"Checked {len(song_ids)} songs and the links of {pages} pages: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
