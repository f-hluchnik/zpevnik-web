"""What the online songbook needs from `songs.json` and `scores.zip` besides the
templates: finding the score images the songs use, checking the links between
songs, and telling lines of chords from lines of lyrics.

Everything here is a pure function of the data, so it is tested without a build
(tests/test_songbook.py). The shape of the data is the songbook repository's
tools/songs.schema.json.
"""

from __future__ import annotations

import io
import re
import sys
import zipfile
from collections.abc import Iterator

SCORE_FILE = re.compile(r"[A-Za-z0-9._-]+\.svg")  # the names the schema allows for a score, plus .svg


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
