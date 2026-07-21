#!/usr/bin/env python3
"""
Static site generator for the songbook site.
Syncs shared theme assets (base.html, style.css) from the main blog repo.
"""

import shutil
import sys
import urllib.error
import urllib.request
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

# Replace with your GitHub username and blog repository name
RAW_BLOG_BASE = "https://raw.githubusercontent.com/f-hluchnik/blog/main"

SITE = {
    "title": "A Notebook of Ordinary Things",
    "description": "Bread, running, books, and other notes from life.",
    "url": "https://zpevnik.hluchnikovi.cz",
}


def sync_shared_assets():
    """Fetch latest base.html and style.css from the main blog repository."""
    assets = [
        (f"{RAW_BLOG_BASE}/templates/base.html", TEMPLATES_DIR / "base.html"),
        (f"{RAW_BLOG_BASE}/static/style.css", STATIC_DIR / "style.css"),
    ]

    print("Syncing shared theme assets from main blog repo...")
    for url, target_path in assets:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BuildScript"})
            with urllib.request.urlopen(req, timeout=5) as response:
                target_path.write_bytes(response.read())
            print(f"  ✓ Updated {target_path.name}")
        except (urllib.error.URLError, TimeoutError) as e:
            if target_path.exists():
                print(f"  ⚠️ Could not fetch {target_path.name} ({e}). Using local cached copy.")
            else:
                print(f"  ❌ Error fetching {target_path.name} and no local copy exists!")
                sys.exit(1)


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


def render(env: Environment, template_name: str, out_path: Path, **context) -> None:
    template = env.get_template(template_name)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(template.render(site=SITE, **context), encoding="utf-8")


def build() -> None:
    # 1. Sync theme assets first
    sync_shared_assets()

    # 2. Re-initialize Jinja env to pick up updated base.html
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

    # 3. Re-create dist directory
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    # 4. Render pages
    pages = load_pages()
    for page in pages:
        out = (
            OUTPUT_DIR / "index.html"
            if page["slug"] == "index"
            else OUTPUT_DIR / page["slug"] / "index.html"
        )
        render(env, "page.html", out, page=page)

    # 5. Copy static assets
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, OUTPUT_DIR / "static")

    print(f"Built {len(pages)} page(s) -> {OUTPUT_DIR}/")


def serve() -> None:
    import functools

    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(OUTPUT_DIR))
    server = HTTPServer(("localhost", 8000), handler)
    print("Serving http://localhost:8000 (Ctrl+C to stop)")
    server.serve_forever()


if __name__ == "__main__":
    build()
    if "--serve" in sys.argv:
        serve()