# Fonts of the chords

Self-hosted: the page makes no request to another site for them. Used by
`.chord` in `static/songbook.css` (`--chord-font`).

| File | What | Licence |
|---|---|---|
| `ibm-plex-sans-condensed-latin-700.woff2` | The letters and digits of the chords. IBM Plex Sans Condensed Bold, the Latin subset of `@fontsource/ibm-plex-sans-condensed` 5.x, unchanged. Its G has a bar and a spur and its C has neither, which the lyrics' font (Alegreya Sans) does not show at chord size. | SIL OFL 1.1, `IBM-Plex-OFL.txt` |
| `dejavu-sans-bold-chord-symbols.woff2` | The five symbols that appear in chords and that no text font of the site has: ♯ U+266F, ♭ U+266D, △ U+25B3, ∘ U+2218, ∅ U+2205. DejaVu Sans Bold 2.37, cut down to those glyphs. Without it each reader's system picks the glyphs. Two `@font-face` rules use it, so that the accidentals (140%) and the other three (115%) are scaled apart: DejaVu draws them light and small for a raised part. | Bitstream Vera licence (DejaVu changes are public domain), `DejaVu-LICENSE.txt`. The licence asks that a modified font does not carry "Bitstream" or "Vera" in its name; it does not. |

The symbols' character set is the set of non-letters in the chords of
`songs.json`. If a release brings a new one, the check below finds it.

## Making the symbols file again

```
pyftsubset DejaVuSans-Bold.ttf \
  --unicodes=U+266D,U+266F,U+25B3,U+2218,U+2205 \
  --layout-features= --no-hinting --flavor=woff2 \
  --output-file=dejavu-sans-bold-chord-symbols.woff2
```

(`pyftsubset` is part of `fonttools`; WOFF2 needs `brotli`.) The unicode
ranges of the two faces that use it (`Chord Accidentals`, `Chord Symbols`) must list the same characters together.

## Checking that the fonts cover the chords

`check_site.py` (the release check) reads the unicode-ranges of `songbook.css`
and the chords of `songs.json`, and fails when a character of a chord is
neither ASCII, nor the ellipsis (in the Latin subset of Plex), nor in a range.
