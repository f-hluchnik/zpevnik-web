# zpevnik-web — Ještě mi chvilku zpívej

A single-page static site at
[zpevnik.hluchnikovi.cz](https://zpevnik.hluchnikovi.cz) that hands out the
songbook PDFs. No framework, no database, no server: `build.py` reads Markdown
and writes plain HTML into `dist/`.

Sibling repo: [blog](https://f.hluchnikovi.cz) — a separate, standalone site
with its own look, but the same layout, the same `build.py` structure, and the
same section order in its stylesheet. Read one and you can read the other.
Nothing is shared at build time; the two link to each other only by ordinary
hyperlinks (this site's footer, and the blog's "Projekty" page).

## Layout

```
content/pages/*.md   one file per page   (index.md is the front page)
templates/*.html     one file per shape  (see below)
static/              CSS, JS, icons — copied to dist/static/ as-is
static/files/        the songbook PDFs
build.py             reads all of the above, writes dist/
dist/                the entire website; gitignored, rebuilt every run
```

## The mental model

Two kinds of thing, and the templates follow directly from them:

| | |
|---|---|
| **Content** you author | `content/pages/` |
| **Templates**, one per shape | single item: `page.html` |

There is no index template — no posts, no tags, no archives to derive. The
blog has those; this site does not, and that is the only structural
difference between the two `build.py` files. Partials start with an underscore
(`_theme-toggle.html`) and are `include`d, not extended.

## Adding a page

Create a file in `content/pages/`. `index.md` is the front page and lands at
`dist/index.html`; anything else gets its own directory, so `about.md` becomes
`/about/`.

```markdown
---
title: O zpěvníku
---

Text in Markdown.
```

The front page needs no `title` — it uses `SITE["title"]`.

There is no navigation bar: with one page there is nothing to navigate. A
second page will build and be reachable at its URL, but you have to link to it
yourself from the front page.

## Updating the PDFs

Replace the files in `static/files/`, keeping the names (`zpevnik_last.pdf`,
`zpevnik_lidovky.pdf`, `zpevnik_koledy.pdf`). The download buttons on the front
page point at those paths and need no change.

## Previewing locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python build.py --serve
```

Open <http://localhost:8000>. Re-run after any edit — there is no auto-reload,
which is one less moving part to maintain.

## Editing the design

Everything visual is in `static/style.css`. Colours are declared once as
custom properties at the top, each with its light and dark value side by side
via `light-dark()`; nothing below that block hardcodes a colour. The
light/dark toggle is `static/theme.js`, byte-identical to the blog's copy.

Footer alignment follows the header: centred here, left-aligned in the blog.

Czech strings live in the templates that show them, not in a config dict. The
site is only ever going to be in Czech.

## What the odd files are for

- **`static/theme.js`** — the light/dark *toggle*, and only the toggle. Dark
  mode itself needs no JavaScript: `color-scheme: light dark` plus the
  `light-dark()` tokens already follow the reader's system setting. This file
  exists so someone on a light OS can read the site dark anyway. It is loaded
  render-blocking from `<head>` on purpose — it has to set `data-theme` before
  first paint, or a dark-mode reader sees a white flash. Deleting it and
  `templates/_theme-toggle.html` would leave dark mode fully working.
- **`static/site.webmanifest`** — only used when someone adds the site to a
  phone home screen on Android; it supplies the name, icon and colours there.
  iOS uses the `apple-touch-icon` link instead. Invisible to normal visitors,
  and worth keeping mainly because this is a page people pin to a phone to
  reach the PDFs.
- **`templates/404.html`** — GitHub Pages serves `dist/404.html` for any path
  it cannot match. It has no Markdown file behind it because there is nothing
  to author. Without it, a mistyped URL gets GitHub's generic English error
  page instead of this site.

## Deploying

`.github/workflows/deploy.yml` builds on every push and every pull request,
but publishes to GitHub Pages only from `main`. A branch or a pull request
therefore tells you the site still builds, without touching what is live.

The custom domain is derived from `SITE["url"]` — `build.py` writes
`dist/CNAME` from it, so the domain is configured in exactly one place. In the
repo's **Settings → Pages**, set **Source** to **GitHub Actions**, then point
your DNS at GitHub Pages per
[their instructions](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site).
