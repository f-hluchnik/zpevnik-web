#!/usr/bin/env python3
"""Static site generator for the songbook site.

Two kinds of thing:

  * content   -- Markdown you write, in `content/pages/`. One file per page;
                 `index.md` becomes the front page.
  * templates -- Jinja2 HTML in `templates/`, one per *shape*: `page.html` for
                 an authored page; the online songbook is built from
                 `songs.json`, not from Markdown, with `contents.html`,
                 `artists.html`, `artist.html` and `song.html`.

`build()` reads the content and writes plain HTML into `dist/`. That directory
is the entire website; it is gitignored and rebuilt from scratch every run.
The songbook PDFs, `songs.json` and `scores.zip` (the data of the online
songbook) are not in this repository: every build downloads them from the
release of the songbook repo named in `version.txt` (see EDITION_DOWNLOADS,
SONGS_JSON_ASSET and SCORES_ASSET).

Standalone from the blog: nothing is fetched from the blog repo at build time,
and the two sites look deliberately different. They are linked only by ordinary
hyperlinks -- this site's footer, and the blog's "Projekty" page. What they do
share is the shape of this file: it is a subset of the blog's build.py, with
the same names in the same order.

Usage:
    python build.py                          # build into dist/
    python build.py --serve                  # build, then serve dist/ on localhost:8000
    python build.py --songs-json FILE        # use a local songs.json, not the release's
    python build.py --scores-zip FILE        # use a local scores.zip, not the release's
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from html import escape
from datetime import date
from functools import partial
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from songbook import (
    artist_references,
    book_neighbours,
    check_free_ids,
    check_scores_present,
    check_see_links,
    is_chord_only_line,
    read_score_images,
    search_entry,
)

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

ROOT = Path(__file__).parent
PAGES_DIR = ROOT / "content" / "pages"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
OUTPUT_DIR = ROOT / "dist"
DOWNLOAD_DIR = ROOT / "build"  # release assets used at build time but not published; gitignored

SERVE_ADDRESS = ("localhost", 8000)

VERSION_FILE = ROOT / "version.txt"  # written by the songbook repo's CI after each release

# Where the PDFs come from: the release `v<version.txt>` of the songbook repo.
SONGBOOK_RELEASE_URL = "https://github.com/f-hluchnik/zpevnik/releases/download/v{version}/{asset}"
DOWNLOAD_TIMEOUT_SECONDS = 60
PDF_MAGIC = b"%PDF-"
FILES_URL_PATH = "/static/files/"  # where the PDFs are served; static/files/ holds the koledy book

# The data of the online songbook, the contract between the two repositories
# (tools/songs.schema.json in the songbook repo). Read at build time only.
SONGS_JSON_ASSET = "songs.json"
SUPPORTED_SCHEMA_VERSION = 1
SCORES_ASSET = "scores.zip"  # the score images (SVG) the songs show
SCORES_URL_PATH = "/static/scores/"  # where they are served

# Where the online songbook is served (D-167): the index at <path>, a song at
# <path><id>/, the list of artists at <path>interpret/, an artist or a
# collection at <path>interpret/<slug>/ (D-103, D-168) and the search at
# <path>hledat/ (D-170). A song id may be none of these directory names.
SONGBOOK_URL_PATH = "/zpivej/"
ARTISTS_DIRECTORY = "interpret"
ARTISTS_URL_PATH = f"{SONGBOOK_URL_PATH}{ARTISTS_DIRECTORY}/"
SEARCH_DIRECTORY = "hledat"
SEARCH_URL_PATH = f"{SONGBOOK_URL_PATH}{SEARCH_DIRECTORY}/"
RESERVED_DIRECTORIES = (ARTISTS_DIRECTORY, SEARCH_DIRECTORY)

# What the search looks through, written at build time and loaded by the search
# page when it is first used.
SEARCH_INDEX_URL_PATH = "/static/search-index.json"

# A file of the site is asked for as <path>?v=<this many characters of the hash of its
# content>, see asset_url().
CONTENT_VERSION_LENGTH = 8

# The two parts of the site, which the tabs under the header switch between
# (`site_section` of a page); a page of neither, the 404 page, marks no tab.
SECTION_DOWNLOAD = "download"
SECTION_SONGBOOK = "songbook"

# The parts of the songbook, which its own navigation switches between
# (`songbook_section` of a page); a song belongs to the contents.
CONTENTS_SECTION = "contents"
ARTISTS_SECTION = "artists"
SEARCH_SECTION = "search"

# `extra` is a bundle. The part that matters here is md_in_html, which lets the
# raw <details markdown="1"> accordions in index.md still render as Markdown;
# drop it and that content comes out as literal text. `footnotes` is named
# again so MARKDOWN_CONFIG can reach it.
MARKDOWN_EXTENSIONS = ["extra", "footnotes", "sane_lists", "smarty"]

# The two extensions that emit text of their own, which defaults to English.
MARKDOWN_CONFIG = {
    "footnotes": {"BACKLINK_TITLE": "Zpět na odkaz na poznámku {}"},
    "smarty": {
        "substitutions": {
            "left-double-quote": "&bdquo;",  # Czech quotes are „like this“
            "right-double-quote": "&ldquo;",
            "left-single-quote": "&sbquo;",
            "right-single-quote": "&lsquo;",
        }
    },
}


@dataclass(frozen=True)
class EditionDownload:
    """One edition of the songbook offered on the front page."""

    edition: str  # the folder name in editions/ of the songbook repo
    label: str  # the button text
    served_as: str  # the file name under /static/files/

    def asset_name(self, version: str) -> str:
        """The name the songbook CI gives the PDF in the release."""
        return f"zpevnik-{self.edition}-{version}.pdf"


# The first entry is the main button, the others are secondary buttons, in this
# order. Which editions exist is decided by the songbook repo (every folder of
# editions/ is released); which of them this page shows is decided here.
# `zpevnik_last.pdf` is a fixed URL that printed QR codes point to: never rename it.
# When `zpevnik-lite` exists, add it as the first entry and give the full book a
# secondary label.
EDITION_DOWNLOADS = (
    EditionDownload("full", "stáhnout zpěvník", "zpevnik_last.pdf"),
    EditionDownload("lidovky", "zpěvník lidových písniček", "zpevnik_lidovky.pdf"),
)

# "Open in PDF" on a song opens the full book, the first edition above, at the
# song's page (`page` in songs.json is the PDF page index, D-165).
SONGBOOK_PDF_URL = FILES_URL_PATH + EDITION_DOWNLOADS[0].served_as

SITE = {
    "lang": "cs",
    "title": "Ještě mi chvilku zpívej",
    "description": "Zpěvník, který píšu v LaTeXu od roku 2019.",
    "url": "https://zpevnik.hluchnikovi.cz",
    "songbook_path": SONGBOOK_URL_PATH,
    "artists_path": ARTISTS_URL_PATH,
    "search_path": SEARCH_URL_PATH,
    "pdf_path": SONGBOOK_PDF_URL,
    "scores_path": SCORES_URL_PATH,
    "contact_email": "frantahluchnik@gmail.com",  # removal requests (the legal notice in the footer)
}

env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
    # Fail the build on a missing or misspelled variable rather than quietly
    # rendering an empty string -- a missing SITE["title"] once shipped an
    # empty <title> exactly that way.
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)
env.tests["chord_only"] = is_chord_only_line
env.filters["artist_references"] = artist_references


def content_version(content: bytes) -> str:
    """A short name for this content: it changes when the content does."""
    return hashlib.sha256(content).hexdigest()[:CONTENT_VERSION_LENGTH]


def asset_url(name: str) -> str:
    """The URL of a style sheet or script of static/, with the version of its content.

    GitHub Pages lets a browser keep a file for ten minutes, so a visitor who has
    just seen the site could get the new pages with the old style sheet: a new
    URL with every change of the file makes the browser ask for it again."""
    return f"/static/{name}?v={content_version((STATIC_DIR / name).read_bytes())}"


env.globals["asset_url"] = asset_url


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def split_front_matter(raw: str) -> tuple[dict, str]:
    """Split '---\\nyaml\\n---\\nbody' into (metadata, body). A file that only
    opens with a thematic break is returned untouched."""
    if not raw.startswith("---\n") or raw.count("---", 1) == 0:
        return {}, raw
    _, front_matter, body = raw.split("---", 2)
    return yaml.safe_load(front_matter) or {}, body.strip()


def render_markdown(body: str) -> str:
    # A fresh converter per document: a reused Markdown instance carries state
    # between conversions (footnote numbering, most visibly).
    return markdown.markdown(
        body, extensions=MARKDOWN_EXTENSIONS, extension_configs=MARKDOWN_CONFIG
    )


def parse_page(raw: str, path: Path) -> dict:
    """One page's raw source -> a page dict.

    `index.md` is the front page and lands at dist/index.html; every other page
    gets its own directory, so its URL has no .html suffix. `path` is only used
    for its stem (slug) -- for templated pages this is the resolved *.md name,
    not the *.md.tpl source file.
    """
    meta, body = split_front_matter(raw)
    slug = meta.get("slug") or path.stem
    is_home = slug == "index"
    return {
        "title": meta.get("title", SITE["title"] if is_home else slug),
        "slug": slug,
        "is_home": is_home,
        "output_path": Path("index.html") if is_home else Path(slug) / "index.html",
        "content": render_markdown(body),
    }


def read_version() -> str:
    """The songbook version whose release this build publishes."""
    if not VERSION_FILE.exists():
        sys.exit(f"{VERSION_FILE.name} is missing: it names the songbook release to download.")
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def download_links(version: str) -> list[dict]:
    """The front page's download buttons, main one first."""
    return [
        {
            "label": download.label,
            "href": FILES_URL_PATH + download.served_as,
            "filename": download.asset_name(version),
        }
        for download in EDITION_DOWNLOADS
    ]


def load_pages(version: str) -> list[dict]:
    """Load every page in content/pages/.

    A page is either a plain `*.md` file, or a `*.md.tpl` template rendered
    in-memory: __VERSION__ becomes the songbook version and __DOWNLOADS__ the
    edition download buttons. Templates are never written back to disk, so a
    local `python build.py` run leaves the working tree untouched.
    """
    pages = [
        parse_page(path.read_text(encoding="utf-8"), path)
        for path in sorted(PAGES_DIR.glob("*.md"))
    ]

    SITE["version"] = version
    placeholders = {
        "__VERSION__": version,
        "__DOWNLOADS__": env.get_template("_downloads.html").render(
            downloads=download_links(version)
        ),
    }

    for tpl_path in sorted(PAGES_DIR.glob("*.md.tpl")):
        raw = tpl_path.read_text(encoding="utf-8")
        for placeholder, value in placeholders.items():
            raw = raw.replace(placeholder, value)
        md_path = tpl_path.with_suffix("")  # index.md.tpl -> index.md, for slug/stem purposes
        pages.append(parse_page(raw, md_path))

    return pages


# --------------------------------------------------------------------------
# Release assets
# --------------------------------------------------------------------------


def download(url: str) -> bytes:
    """Download one release asset, failing loudly: a site without its data must not go live."""
    try:
        with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError) as error:
        sys.exit(f"Cannot download {url}: {error}\n"
                 "Does the songbook release named in version.txt exist and carry this file?")


def fetch_pdf(url: str) -> bytes:
    """Download one PDF."""
    content = download(url)
    if not content.startswith(PDF_MAGIC):
        sys.exit(f"{url} is not a PDF.")
    return content


def fetch_edition_pdfs(version: str) -> dict[str, bytes]:
    """The PDF of every configured edition from the release, by served file name."""
    return {
        download.served_as: fetch_pdf(
            SONGBOOK_RELEASE_URL.format(version=version, asset=download.asset_name(version))
        )
        for download in EDITION_DOWNLOADS
    }


def parse_songs_document(raw: bytes, source: str) -> dict:
    """The contents of a `songs.json`, checked to be one this build understands."""
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as error:
        sys.exit(f"{source} is not valid JSON: {error}")
    schema_version = document.get("schemaVersion") if isinstance(document, dict) else None
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        sys.exit(f"{source} has schemaVersion {schema_version!r}, but this build reads only "
                 f"{SUPPORTED_SCHEMA_VERSION}: update build.py together with the songbook's schema.")
    return document


def read_release_asset(version: str, asset: str, local_file: Path | None) -> tuple[bytes, str]:
    """An asset of the release, and where it came from (for error messages).
    `local_file` replaces it, for working on a songbook change before it is
    released. A downloaded asset is kept in build/ to look at."""
    if local_file is not None:
        if not local_file.is_file():
            sys.exit(f"{local_file} does not exist.")
        return local_file.read_bytes(), str(local_file)
    url = SONGBOOK_RELEASE_URL.format(version=version, asset=asset)
    content = download(url)
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    (DOWNLOAD_DIR / asset).write_bytes(content)
    return content, url


def load_songs_document(version: str, local_file: Path | None) -> dict:
    """`songs.json` of the release, or `local_file` when given."""
    return parse_songs_document(*read_release_asset(version, SONGS_JSON_ASSET, local_file))


def load_score_images(version: str, local_file: Path | None, songs: list[dict]) -> dict[str, bytes]:
    """The score images of the release (or `local_file`) by file name; stops
    unless it holds every image the songs show."""
    images = read_score_images(*read_release_asset(version, SCORES_ASSET, local_file))
    check_scores_present(songs, images)
    return images


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def render(template_name: str, out_path: Path, site_section: str | None = None, **context) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        env.get_template(template_name).render(
            site=SITE, site_section=site_section, current_year=date.today().year, **context
        ),
        encoding="utf-8",
    )


def render_songbook(document: dict, search_index_url: str) -> None:
    """The online songbook: the index, the artists, the search, and a page per song."""
    songs = document["songs"]
    songs_by_id = {song["id"]: song for song in songs}
    artists = {artist["slug"]: artist for artist in document["artists"]}
    songbook_dir = OUTPUT_DIR / SONGBOOK_URL_PATH.strip("/")
    artists_dir = songbook_dir / ARTISTS_DIRECTORY

    render_page = partial(render, site_section=SECTION_SONGBOOK)

    render_page("search.html", songbook_dir / SEARCH_DIRECTORY / "index.html",
                search_index_url=search_index_url, songbook_section=SEARCH_SECTION)

    render_page("contents.html", songbook_dir / "index.html", sections=document["contents"],
                songs=songs_by_id, songbook_section=CONTENTS_SECTION)

    # An artist without a section has no page, as in the book; the songs name them in plain text.
    artists_with_page = [artist for artist in document["artists"] if artist["section"]]
    render_page("artists.html", artists_dir / "index.html", artists_with_page=artists_with_page,
                songbook_section=ARTISTS_SECTION)
    for artist in artists_with_page:
        render_page("artist.html", artists_dir / artist["slug"] / "index.html", artist=artist,
                    songs=songs_by_id, songbook_section=ARTISTS_SECTION)

    for previous_song, song, next_song in book_neighbours(songs):
        render_page("song.html", songbook_dir / song["id"] / "index.html", song=song, artists=artists,
                    previous_song=previous_song, next_song=next_song,
                    songbook_section=CONTENTS_SECTION)


def search_index_json(document: dict) -> bytes:
    """What the search looks through, one entry per song in book order, as compact JSON."""
    artists = {artist["slug"]: artist for artist in document["artists"]}
    entries = [search_entry(song, artists) for song in document["songs"]]
    return json.dumps(entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def build(songs_json: Path | None = None, scores_zip: Path | None = None) -> None:
    # Parse and download before deleting dist/, so a broken page or an
    # unreachable release leaves the previous build in place instead of an
    # empty directory.
    version = read_version()
    pages = load_pages(version)
    edition_pdfs = fetch_edition_pdfs(version)
    document = load_songs_document(version, songs_json)
    songs = document["songs"]
    search_index = search_index_json(document)
    check_see_links(songs)
    check_free_ids(songs, reserved=RESERVED_DIRECTORIES)
    score_images = load_score_images(version, scores_zip, songs)

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    for page in pages:
        render("page.html", OUTPUT_DIR / page["output_path"], site_section=SECTION_DOWNLOAD, page=page)

    render_songbook(document, f"{SEARCH_INDEX_URL_PATH}?v={content_version(search_index)}")

    # GitHub Pages serves /404.html for any path it cannot match.
    render("404.html", OUTPUT_DIR / "404.html")

    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, OUTPUT_DIR / "static")

    files_dir = OUTPUT_DIR / FILES_URL_PATH.strip("/")
    files_dir.mkdir(parents=True, exist_ok=True)
    for served_as, content in edition_pdfs.items():
        (files_dir / served_as).write_bytes(content)

    search_index_file = OUTPUT_DIR / SEARCH_INDEX_URL_PATH.strip("/")
    search_index_file.parent.mkdir(parents=True, exist_ok=True)
    search_index_file.write_bytes(search_index)

    scores_dir = OUTPUT_DIR / SCORES_URL_PATH.strip("/")
    scores_dir.mkdir(parents=True)
    for file_name, content in score_images.items():
        (scores_dir / file_name).write_bytes(content)

    # Derived from SITE["url"], so the domain is configured in one place
    # instead of also being hardcoded in the deploy workflow.
    (OUTPUT_DIR / "CNAME").write_text(urlparse(SITE["url"]).netloc + "\n", encoding="utf-8")

    print(f"Built {len(pages)} page(s), {len(songs)} song page(s) and {len(edition_pdfs)} PDF(s) "
          f"of v{version} -> dist/")


class SiteRequestHandler(SimpleHTTPRequestHandler):
    """Serves dist/ like GitHub Pages: a path it cannot match gets dist/404.html."""

    def send_error(self, code, message=None, explain=None):
        if code != HTTPStatus.NOT_FOUND:
            super().send_error(code, message, explain)
            return
        page = (OUTPUT_DIR / "404.html").read_bytes()
        self.send_response(HTTPStatus.NOT_FOUND)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(page)


def serve() -> None:
    handler = partial(SiteRequestHandler, directory=str(OUTPUT_DIR))
    print("Serving http://{}:{}  (Ctrl+C to stop)".format(*SERVE_ADDRESS))
    try:
        HTTPServer(SERVE_ADDRESS, handler).serve_forever()
    except KeyboardInterrupt:
        print()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the songbook site into dist/.")
    parser.add_argument("--serve", action="store_true", help="serve dist/ on localhost after building")
    parser.add_argument("--songs-json", type=Path, metavar="FILE",
                        help="read this songs.json instead of the release's")
    parser.add_argument("--scores-zip", type=Path, metavar="FILE",
                        help="read this scores.zip instead of the release's")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_arguments()
    build(arguments.songs_json, arguments.scores_zip)
    if arguments.serve:
        serve()
