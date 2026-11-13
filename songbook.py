"""What the online songbook needs from `songs.json` and `scores.zip` besides the
templates: finding the score images the songs use, checking the links between
songs, telling lines of chords from lines of lyrics, the pieces a line is drawn
from (how much of a chord's text stands in its column), the neighbours of a
song in the book, and what the search looks through.

Everything here is a pure function of the data, so it is tested without a build
(tests/test_songbook.py). The shape of the data is the songbook repository's
tools/songs.schema.json.
"""

from __future__ import annotations

import io
import math
import re
import sys
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import ClassVar

SCORE_FILE = re.compile(r"[A-Za-z0-9._-]+\.svg")  # the names the schema allows for a score, plus .svg

# How much text a chord's column holds (split_head, D-176). The build knows
# characters, not widths, so these are estimates; one that is too short only
# widens a space after the head, it never lets two chords collide.
CHORD_LETTER_WIDTH = 1.3   # a bold chord letter is about 1.3 letters of the text; a raised
                           # "7" counts as a whole one, which only lengthens the head a little
SEPARATOR_CHARACTERS = 2   # --chord-sep (0.5 em) is about one letter; with one more, a head
                           # that is too short is rare (104 of 7,800 instead of 558, D-176)
EM_PER_CHARACTER = 0.5     # the book's unit: \gap{n} is n characters of 0.5 em (D-123)


def body_lines(song: dict) -> Iterator[dict]:
    """Every line of a song, whichever block it is in."""
    for item in song["body"]:
        if item["type"] == "cueBlock":
            yield item["line"]
        elif item["type"] in ("block", "speakerBlock"):
            yield from item["lines"]


def score_names(songs: list[dict]) -> set[str]:
    """The names of the score images the songs show."""
    return {
        item["name"]
        for song in songs
        for line in body_lines(song)
        for item in line["items"]
        if item["type"] == "score"
    }


def is_chord_only_line(line: dict) -> bool:
    """A line of chords with no words at all (an intro, `\\chords{}` in the book).

    It is set in the line of text, as the book does; a chord above empty text
    would leave an empty row under it."""
    segments = [item for item in line["items"] if item["type"] == "segment"]
    return bool(segments) and not any(segment["lyrics"] for segment in segments)


def chord_head_length(chord: list[dict]) -> int:
    """How many characters of text cover a chord and the separator after it."""
    characters = sum(len(part["text"]) for part in chord)
    return math.ceil(characters * CHORD_LETTER_WIDTH) + SEPARATOR_CHARACTERS


def has_words(parts: Iterable[dict]) -> bool:
    """Whether a text has a word in it, not only spaces, pauses or marks."""
    return any(part["type"] == "run" and part["text"].strip() for part in parts)


def split_run(part: dict, offset: int) -> tuple[list[dict], list[dict]]:
    """A run cut at `offset` into the runs before and after it (none where empty)."""
    before, after = part["text"][:offset], part["text"][offset:]
    return ([{**part, "text": before}] if before else []), ([{**part, "text": after}] if after else [])


def split_head(chord: list[dict], lyrics: list[dict]) -> tuple[list[dict], list[dict]]:
    """The text under a chord cut into the head, which stands in the chord's
    column, and the tail, which flows after it (D-176).

    The head is the shortest run of whole words that covers the chord
    (`chord_head_length`): the text is cut at a space (not a no-break space),
    and the tail starts with that space and has a word in it. A text that is
    not longer than that is all head, and the tail is empty. A pause counts by
    its length, a footnote mark not at all. The column is still
    max(head, chord + separator), so a guess that is too short widens a space
    but never lets two chords collide (D-123).
    """
    needed = chord_head_length(chord)
    length = 0.0
    for index, part in enumerate(lyrics):
        if part["type"] == "gap":
            length += part["em"] / EM_PER_CHARACTER
        if part["type"] != "run":
            continue
        for offset, character in enumerate(part["text"]):
            if character == " " and length >= needed:
                head_end, tail_start = split_run(part, offset)
                tail = tail_start + lyrics[index + 1:]
                if has_words(tail):
                    return lyrics[:index] + head_end, tail
            length += 1
    return lyrics, []


# The pieces a line of a song is drawn from (layout_line); the template draws
# each by its `kind`.

@dataclass(frozen=True)
class Column:
    """A chord and the head of its text, as wide as the wider of the two."""
    kind: ClassVar[str] = "column"
    chord: list[dict]
    text: list[dict]
    hyphen_room: bool  # the text ends inside a word: the gap after it may hold a hyphen
    chord_run: bool    # no text under the chord: the next chord is farther away


@dataclass(frozen=True)
class Word:
    """Columns that share a word: they go to the next row together, as a hyphen
    cannot be shown at a break between them."""
    kind: ClassVar[str] = "word"
    columns: tuple[Column, ...]


@dataclass(frozen=True)
class Flow:
    """Text outside a column, which wraps at its spaces: the tail of a chord's
    text, or text with no chord. Where it ends inside a word, a soft hyphen
    lets the line break there with a hyphen, as the book's does."""
    kind: ClassVar[str] = "flow"
    text: list[dict]
    soft_hyphen: bool


@dataclass(frozen=True)
class Mark:
    """Anything else on a line (a repeat sign, a cue, a note, a speaker, a score)."""
    kind: ClassVar[str] = "mark"
    item: dict


Piece = Column | Word | Flow | Mark


def layout_line(items: list[dict]) -> list[Piece]:
    """The pieces of a line of a song (D-176): each chord with the head of its
    text in a column and the tail flowing after it; text without a chord
    flowing; columns that share a word in one group."""
    pieces: list[Piece] = []
    word: list[Column] = []  # columns of a word that goes on in the next column

    def place_word() -> None:
        if word:
            pieces.append(word[0] if len(word) == 1 else Word(tuple(word)))
            word.clear()

    for item in items:
        if item["type"] != "segment":
            place_word()
            pieces.append(Mark(item))
            continue
        if item["chord"] is None:
            place_word()
            pieces.append(Flow(item["lyrics"], soft_hyphen=item["endsInWord"]))
            continue
        head, tail = split_head(item["chord"], item["lyrics"])
        word.append(Column(item["chord"], head, hyphen_room=item["endsInWord"] and not tail,
                           chord_run=not item["lyrics"]))
        if item["endsInWord"] and not tail:
            continue
        place_word()
        if tail:
            pieces.append(Flow(tail, soft_hyphen=item["endsInWord"]))
    place_word()
    return pieces


def plain_text(parts: list[dict]) -> str:
    """A text (runs, gaps, footnote marks) as plain words: a pause is a space,
    a footnote mark is nothing, and any run of spaces is one."""
    pieces = (
        part["text"] if part["type"] == "run" else " " if part["type"] == "gap" else ""
        for part in parts
    )
    return " ".join("".join(pieces).split())


def lyrics_lines(song: dict) -> list[str]:
    """The lyrics of a song, a plain line each: the words a singer remembers,
    without chords, labels or notes. The text under a chord and the text under
    the next one are joined, so a word the chord stands in is whole again."""
    lines = (
        plain_text([part for item in line["items"] if item["type"] == "segment" for part in item["lyrics"]])
        for line in body_lines(song)
    )
    return [line for line in lines if line]


def search_entry(song: dict, artists: dict[str, dict]) -> dict:
    """What the search knows of a song (`artists` by slug, as in the document)."""
    return {
        "id": song["id"],
        "title": song["tocTitle"],
        "altTitles": song["altTitles"],
        "artists": [label or artists[slug]["linkLabel"] for slug, label in artist_references(song)],
        "lyrics": "\n".join(lyrics_lines(song)),
    }


def artist_references(song: dict) -> list[tuple[str, str | None]]:
    """The artists, then the collections, a song belongs to, as (slug, label).
    The label is the song's own wording of the artist, or None for the registry's."""
    return [(artist["slug"], artist["label"]) for artist in song["artists"]] + [
        (slug, None) for slug in song["collections"]
    ]


def book_neighbours(songs: list[dict]) -> Iterator[tuple[dict | None, dict, dict | None]]:
    """Each song with the one before and the one after it in book order (None at the ends)."""
    for index, song in enumerate(songs):
        previous_song = songs[index - 1] if index > 0 else None
        next_song = songs[index + 1] if index + 1 < len(songs) else None
        yield previous_song, song, next_song


def check_see_links(songs: list[dict]) -> None:
    """Stop the build if a song points to a song that has no page."""
    known = {song["id"] for song in songs}
    for song in songs:
        for target in song["see"]:
            if target["id"] not in known:
                sys.exit(f"Song {song['id']!r} refers to {target['id']!r}, which is not in songs.json.")


def read_score_images(raw: bytes, source: str) -> dict[str, bytes]:
    """The SVG images of `scores.zip` by file name. Only plain `<name>.svg`
    entries are taken, so no entry can write outside the folder they go to."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            return {
                name: archive.read(name)
                for name in archive.namelist()
                if SCORE_FILE.fullmatch(name)
            }
    except zipfile.BadZipFile:
        sys.exit(f"{source} is not a zip file.")


def check_scores_present(songs: list[dict], images: dict[str, bytes]) -> None:
    """Stop the build if a song shows a score that the zip lacks."""
    missing = sorted(name for name in score_names(songs) if f"{name}.svg" not in images)
    if missing:
        sys.exit(f"scores.zip lacks the image of: {', '.join(missing)}")


def check_free_ids(songs: Iterable[dict], reserved: Iterable[str]) -> None:
    """Stop the build if a song's page would take the place of a page that is not a song's."""
    taken = sorted({song["id"] for song in songs} & set(reserved))
    if taken:
        sys.exit(f"Song id(s) {', '.join(map(repr, taken))} clash with pages of the online songbook.")
