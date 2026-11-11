#!/usr/bin/env python3
"""Static site generator for the songbook site.

Two kinds of thing:

  * content   -- Markdown you write, in `content/pages/`. One file per page;
                 `index.md` becomes the front page.
  * templates -- Jinja2 HTML in `templates/`, one per *shape*. There is only
                 one shape here (`page.html`), because there is nothing to
                 index: no posts, no tags, no archives.

`build()` reads the content and writes plain HTML into `dist/`. That directory
is the entire website; it is gitignored and rebuilt from scratch every run.
The songbook PDFs are not in this repository: every build downloads them from
the release of the songbook repo named in `version.txt` (see EDITION_DOWNLOADS).

Standalone from the blog: nothing is fetched from the blog repo at build time,
and the two sites look deliberately different. They are linked only by ordinary
hyperlinks -- this site's footer, and the blog's "Projekty" page. What they do
share is the shape of this file: it is a subset of the blog's build.py, with
the same names in the same order.

Usage:
    python build.py            # build into dist/
    python build.py --serve    # build, then serve dist/ on localhost:8000
"""

from __future__ import annotations

import shutil
import sys
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from html import escape
from datetime import date
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

ROOT = Path(__file__).parent
PAGES_DIR = ROOT / "content" / "pages"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
OUTPUT_DIR = ROOT / "dist"

SERVE_ADDRESS = ("localhost", 8000)

VERSION_FILE = ROOT / "version.txt"  # written by the songbook repo's CI after each release

# Where the PDFs come from: the release `v<version.txt>` of the songbook repo.
SONGBOOK_RELEASE_URL = "https://github.com/f-hluchnik/zpevnik/releases/download/v{version}/{asset}"
DOWNLOAD_TIMEOUT_SECONDS = 60
PDF_MAGIC = b"%PDF-"
FILES_URL_PATH = "/static/files/"  # where the PDFs are served; static/files/ holds the koledy book

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

SITE = {
    "lang": "cs",
    "title": "Ještě mi chvilku zpívej",
    "description": "Zpěvník, který píšu v LaTeXu od roku 2019.",
    "url": "https://zpevnik.hluchnikovi.cz",
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


def fetch_pdf(url: str) -> bytes:
    """Download one PDF, failing loudly: a site without its PDFs must not go live."""
    try:
        with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            content = response.read()
    except (urllib.error.URLError, TimeoutError) as error:
        sys.exit(f"Cannot download {url}: {error}\n"
                 "Does the songbook release named in version.txt exist and carry this file?")
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


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def render(template_name: str, out_path: Path, **context) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        env.get_template(template_name).render(
            site=SITE, current_year=date.today().year, **context
        ),
        encoding="utf-8",
    )


def build() -> None:
    # Parse and download before deleting dist/, so a broken page or an
    # unreachable release leaves the previous build in place instead of an
    # empty directory.
    version = read_version()
    pages = load_pages(version)
    edition_pdfs = fetch_edition_pdfs(version)

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    for page in pages:
        render("page.html", OUTPUT_DIR / page["output_path"], page=page)

    # GitHub Pages serves /404.html for any path it cannot match.
    render("404.html", OUTPUT_DIR / "404.html")

    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, OUTPUT_DIR / "static")

    files_dir = OUTPUT_DIR / FILES_URL_PATH.strip("/")
    files_dir.mkdir(parents=True, exist_ok=True)
    for served_as, content in edition_pdfs.items():
        (files_dir / served_as).write_bytes(content)

    # Derived from SITE["url"], so the domain is configured in one place
    # instead of also being hardcoded in the deploy workflow.
    (OUTPUT_DIR / "CNAME").write_text(urlparse(SITE["url"]).netloc + "\n", encoding="utf-8")

    print(f"Built {len(pages)} page(s) and {len(edition_pdfs)} PDF(s) of v{version} -> dist/")


def serve() -> None:
    handler = partial(SimpleHTTPRequestHandler, directory=str(OUTPUT_DIR))
    print("Serving http://{}:{}  (Ctrl+C to stop)".format(*SERVE_ADDRESS))
    try:
        HTTPServer(SERVE_ADDRESS, handler).serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    build()
    if "--serve" in sys.argv:
        serve()
