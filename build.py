#!/usr/bin/env python3
"""
Static site generator for the songbook site.

Same idea as the blog's build.py: Markdown + a bit of YAML front matter,
rendered through Jinja2 templates, written to dist/. This site is simpler
than the blog -- it's really just one page -- so there are no posts or
tags, only "pages". The one thing that differs from the blog's build.py:
the page named "index" is written straight to dist/index.html instead of
dist/<slug>/index.html, since this page IS the site's root.

Usage:
    python build.py          # build the site into dist/
    python build.py --serve  # build, then serve dist/ at http://localhost:8000
"""

import shutil
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).parent
PAGES_DIR = ROOT / "content" / "pages"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
OUTPUT_DIR = ROOT / "dist"

SITE = {
    "title": "A Notebook of Ordinary Things",
    "description": "Bread, running, books, and other notes from life.",
    "url": "https://f.hluchnikovi.cz",
}

env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def split_front_matter(raw: str) -> tuple[dict, str]:
    if not raw.startswith("---"):
        return {}, raw
    _, fm_raw, body_raw = raw.split("---", 2)
    meta = yaml.safe_load(fm_raw) or {}
    return meta, body_raw.strip()


def parse_page(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    meta, body = split_front_matter(raw)
    html = markdown.markdown(body, extensions=["extra", "sane_lists", "smarty"])
    return {
        "title": meta.get("title", path.stem.replace("-", " ").title()),
        "slug": path.stem,
        "content": html,
    }


def load_pages() -> list[dict]:
    return [parse_page(p) for p in sorted(PAGES_DIR.glob("*.md"))]


def render(template_name: str, out_path: Path, **context) -> None:
    template = env.get_template(template_name)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(template.render(site=SITE, **context), encoding="utf-8")


def build() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    pages = load_pages()

    for page in pages:
        # The "index" page is the whole site -- write it to the root,
        # not to a subfolder like every other page would get.
        out = (
            OUTPUT_DIR / "index.html"
            if page["slug"] == "index"
            else OUTPUT_DIR / page["slug"] / "index.html"
        )
        render("page.html", out, page=page)

    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, OUTPUT_DIR / "static")

    print(f"Built {len(pages)} page(s) -> {OUTPUT_DIR}/")


def serve() -> None:
    import functools

    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(OUTPUT_DIR))
    server = HTTPServer(("localhost", 8000), handler)
    print("Serving http://localhost:8000  (Ctrl+C to stop)")
    server.serve_forever()


if __name__ == "__main__":
    build()
    if "--serve" in sys.argv:
        serve()