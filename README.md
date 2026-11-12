# zpevnik-web — Ještě mi chvilku zpívej

A single-page static site at
[zpevnik.hluchnikovi.cz](https://zpevnik.hluchnikovi.cz) that hands out the
songbook PDFs. No framework, no database, no server: `build.py` reads Markdown
and writes plain HTML into `dist/`.

Sibling repo: [blog](https://f.hluchnikovi.cz) — a separate, standalone site
with its own look, but the same layout, the same `build.py` structure, and the
same section order in its stylesheet. Read one and you can read the other.
Nothing is shared at build time; the blog links to this site from its
"Projekty" page.

## Layout

```
content/pages/*.md   one file per page   (index.md is the front page)
templates/*.html     one file per shape  (see below)
songbook.py          helpers of the song pages (tested in tests/)
static/              CSS, JS, icons — copied to dist/static/ as-is
static/files/        the koledy songbook (the other PDFs are downloaded, see below)
version.txt          the songbook release this build publishes (written by its CI)
tests/               unit tests of build.py (standard library only)
build.py             reads all of the above, writes dist/
build/               songs.json downloaded from the release; gitignored, not published
dist/                the entire website; gitignored, rebuilt every run
```

## The mental model

Two kinds of thing, and the templates follow directly from them:

| | |
|---|---|
| **Content** you author | `content/pages/` |
| **Templates**, one per shape | authored page: `page.html`; songbook: `contents.html`, `artists.html`, `artist.html`, `song.html` (all on `songbook_base.html`) |

The songs are a third kind of thing: data from the release (`songs.json`, see
below), not content you author. The blog has posts, tags and archives; this
site has the front page and the songbook. Partials start with an underscore
(`_theme-toggle.html`, `_song.html`, `_entries.html`, `_songbook-nav.html`) and
are `include`d or imported, not extended.

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

## The songbook PDFs

The PDFs are not stored here. The songbook repository
([zpevnik](https://github.com/f-hluchnik/zpevnik)) attaches the PDF of every
edition to each release as `zpevnik-<edition>-<version>.pdf`, and after the
release it writes the version to `version.txt` here. Every `build.py` run
downloads the PDFs of the release `v<version.txt>` into `dist/static/files/`;
that push to `main` is also what updates the live site. Nobody updates a PDF
by hand.

Which editions the front page shows is the list `EDITION_DOWNLOADS` in
`build.py`:

| field | meaning |
|---|---|
| `edition` | the folder name in the songbook's `editions/` (it names the release asset) |
| `label` | the button text |
| `served_as` | the file name under `/static/files/` |

The first entry is the main button, the others are secondary buttons next to
the koledy one. **`zpevnik_last.pdf` is a fixed URL** (printed QR codes point
to it), so the full book keeps that name whatever its button looks like.
To show a new edition, add one line; when `zpevnik-lite` exists, make it the
first entry and give the full book a secondary label.

The build fails, and the previous `dist/` stays, if `version.txt` is missing or
a release asset cannot be downloaded or is not a PDF. The koledy songbook is
not an edition of the songbook: it is a plain file in `static/files/`, replaced
by hand, keeping its name.

## `songs.json`, the data of the online songbook

The online songbook (W2 onwards) is built from `songs.json`, which the
songbook repository writes from the same LaTeX files as the PDF and attaches to
the same release. Every `build.py` run downloads it from the release
`v<version.txt>` into `build/` (gitignored, and not published: it is 5 MB) and
checks its `schemaVersion`. Its shape is the contract between the two
repositories, `tools/songs.schema.json` in the songbook repository; the
songbook's CI validates the whole file against it before releasing, so this
build only checks the version it understands (`SUPPORTED_SCHEMA_VERSION`). A
change of the shape raises that version, and `build.py` has to be updated with
it.

The build fails, like for a PDF, if the file is missing from the release, is not
JSON or has another `schemaVersion`.

The score images (the `score` items of the songs) come the same way from
`scores.zip` of the release, and are served at `/static/scores/<name>.svg`. The
build also fails if a song shows a score that the zip lacks, or if a song
refers to a song that is not in `songs.json`.

To work on the site with files that are not released yet (for example those of
a songbook working copy, made by `make json`), name them:

```bash
python build.py --songs-json ../zpevnik/build/songs.json --scores-zip FILE
```

## The online songbook

The songbook lives under `/zpivej/` (`SONGBOOK_URL_PATH` in `build.py`, D-167).
Every page of it extends `templates/songbook_base.html`: its own stylesheet
(`static/songbook.css`), `<meta name="robots" content="noindex">` and its own
navigation (Písničky · Interpreti · Hledat), under the tabs of the site. The pages:

| URL | what | template |
|---|---|---|
| `/zpivej/` | the index: every song and every alternative title, by letter | `contents.html` |
| `/zpivej/<id>/` | one song | `song.html`, with the macros of `_song.html` that follow the shape of `songs.json` |
| `/zpivej/interpret/` | the artists and collections | `artists.html` |
| `/zpivej/interpret/<slug>/` | the songs of one artist or collection | `artist.html` |
| `/zpivej/hledat/` | the search | `search.html`, `static/search.js` |

**The order is the data's.** The index is the `contents` of `songs.json` and an
artist's songs are its `entries`, as the book prints them (Czech collation,
D-107); the build never sorts. An alternative title is shown as in the book:
*the other title* (the song's own). The previous and next song on a song page
are the neighbours in `songs` (book order). A song id may not be `interpret` or
`hledat` (the build stops), and an artist whose registry entry has no section (`section`
is false) has no page and is named in plain text.

The page of one song or one artist marks no item of the songbook's row
(`songbook_section` is `None`): it has its own title and, above it, a muted link
up to its list ("← Všechny písničky", "← Všichni interpreti",
`templates/_up-link.html`), so that the row never looks like a "you are here"
that cannot be clicked.

A song page links its artists and collections, and "otevřít v PDF" opens the
full book (`zpevnik_last.pdf`) at the song's `page`, which is the PDF page
index (D-165). `#page=N` is the usual open parameter of browser PDF viewers;
it has not been tried on a phone, whose viewer may ignore it.

**The search** (D-170) looks through the title, the other titles, the artists
and the lyrics of every song. `build.py` writes them as
`static/search-index.json` (one entry per song in book order; `search_entry` in
`songbook.py`, which joins the text under the chords back into whole lines and
leaves out chords, labels and notes): about 680 kB, 260 kB gzipped. Only the
search page fetches it, when its field is first used (it asks for the focus, so
that is when the page opens), and the script keeps it in memory. `static/search.js` splits the query into words, ignores case and
diacritics (Unicode NFD, so `ceresne` finds *Čerešně*), and finds a song when
every word of the query is the beginning of a word in its title, other titles,
artists or lyrics (`jede` finds `jede`, `jeden` and `jedeme`, not `pojedeme`;
punctuation is a space, so `ain't` is the words `ain` and `t`). The order: the title has all the words, then
the title and other titles, then with the artists, then a line of the lyrics
with all the words together, then the words found apart; within each rank the
songs stay in book order. The results come in two groups (D-173): *V názvu nebo
u interpreta* (the first three ranks) and *V textu* (the lyrics), each with its
number of songs; a song is in the group of its best rank only, and an empty
group is not shown. A hit in the lyrics shows the line, with the matched words
in bold; the group of the lyrics shows its first 10 songs, and a button
*Zobrazit všech N* the rest. A hit in another title shows *též: …*. The query is kept in the address (`?q=`), so the back
button of the browser returns from a song to the results. Without JavaScript
the page says so and links to the index and the artists. There is no library;
the page has been tried in a browser, but there are no automated tests of
`search.js`.

**Versioned URLs.** GitHub Pages lets a browser keep a file for ten minutes,
so a visitor who has just seen the site could get new pages with the old style
sheet (after the search was added, the search page then looked unstyled: a tiny
box and a numbered list). The style sheets, the scripts and the search index are
therefore asked for as `<path>?v=<hash of the content>`: `asset_url()` in
`build.py` (a global of the templates) makes it for the files of `static/`, and
the index gets its own. The icons and the PDFs keep their plain URLs; the PDF
`zpevnik_last.pdf` must (printed QR codes).

**Two levels of navigation.** The tabs *Stáhnout* and *Zobrazit online*
(`templates/_site-nav.html`, in `base.html`) are on every page of the site and
mark the part the reader is in (`site_section`: `SECTION_DOWNLOAD`,
`SECTION_SONGBOOK` in `build.py`; the 404 page marks none). Only under
`/zpivej/` a second row (`_songbook-nav.html`, `songbook_section`) switches
between the index, the artists and the search. They are plain links to separate pages, so
they work without JavaScript and keep the `noindex` of the songbook to its own
pages; they look like tabs but are not ARIA tabs. `404.html` links to the
index as well.

**The chord rule** (D-123) is in `songbook.css`, and needs no JavaScript. A
chord and its text are an inline-block, as wide as the wider of the text and
the chord plus 0.5 em (the chord's padding); chords without text are 1 em
apart; a pause (`gap`) is a fixed space whose width in em comes from the data.
The spaces of the text are kept (`white-space: pre-wrap`). A line of chords
only is set in the line of text, as in the book.
One difference from the book: where a chord stands inside a word, the book
widens the gap to hold a hyphen. CSS cannot widen it only then, so the hyphen
is shown if the gap, which the chord's width makes, is at least 0.4 em wide,
and a narrower gap stays empty. A word that continues without a gap has no
hyphen, in the book and here.

**The font size** buttons (`static/songbook.js`) are hidden without JavaScript;
the choice is remembered in the browser. The song reads the same without them.

**Keep the screen on** (`static/wake-lock.js`, D-174): the button *Nezhasínat
displej* on a song uses the Screen Wake Lock API. It is hidden without
JavaScript and where the browser has no such API (it needs https, or
`localhost`). The browser drops the lock when the page is hidden, so the script
asks again when the page is shown. The choice is kept for the tab
(`sessionStorage`) and the next song takes it over; a closed tab forgets it. If
the browser refuses (low battery, or a request that is not from a tap, which
Safari has done), the button goes back to off. Tried with Chromium and a
replacement of the API; not on a real phone. There are no automated tests.

**An unknown song** (`/zpivej/<anything else>`) gets `404.html`, as every path
GitHub Pages cannot match does; `python build.py --serve` does the same.

## Tests

```bash
python -m unittest discover tests
```

CI runs them before the build. They use only the standard library.

## Previewing locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python build.py --serve
```

Open <http://localhost:8000>. Re-run after any edit — there is no auto-reload,
which is one less moving part to maintain. Each run downloads the PDFs and
`songs.json` (about 11 MB) from GitHub, so it needs a network connection.

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
