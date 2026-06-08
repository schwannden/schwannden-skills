#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["yt-dlp"]
# ///
"""Extract a YouTube MANUAL subtitle and convert it to plain text.

RUN THIS (do not just read it):

    uv run scripts/yt_subs_to_txt.py <url-or-id> <out.txt> [--lang en]

Subtitle-first is the fastest, most accurate way to get a transcript: a
human-authored manual subtitle is effectively a gold transcript. This script
downloads ONLY the manual subtitle (never the auto-generated captions) in the
requested language and converts the VTT/SRT cues to plain text:

  - timestamps and cue numbers are stripped,
  - cue text is joined with newlines,
  - duplicate consecutive lines are collapsed.

If no MANUAL subtitle exists in the requested language, this prints a clear
message and exits NON-ZERO, so the caller knows to fall back to an audio
pipeline (download audio with yt-dlp, then transcribe locally).
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import tempfile


def _load_ydl():
    """Import YoutubeDL lazily so --help works without the dependency."""
    try:
        from yt_dlp import YoutubeDL
    except ImportError:  # pragma: no cover - dependency resolved by uv
        sys.stderr.write(
            "error: yt-dlp is not available. Run this script with `uv run` so "
            "the PEP 723 inline dependencies are resolved.\n"
        )
        sys.exit(2)
    return YoutubeDL


def normalize_id(url_or_id: str) -> str:
    """Accept a bare video id or any YouTube URL; yt-dlp handles both."""
    return url_or_id.strip()


def list_manual_sub_langs(url: str) -> list[str]:
    """Return the language codes that have a MANUAL (not automatic) subtitle."""
    YoutubeDL = _load_ydl()
    opts = {"quiet": True, "skip_download": True, "no_warnings": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    # `subtitles` are manual/human; `automatic_captions` are YouTube ASR.
    return sorted((info.get("subtitles") or {}).keys())


def pick_lang(available: list[str], want: str) -> str | None:
    """Choose the best available manual-sub language code for `want`.

    Matches exact ('en'), then any regional/orig variant ('en-US', 'en-GB',
    'en-orig'), preferring the shortest (closest to the base language).
    """
    if want in available:
        return want
    variants = [c for c in available if c == want or c.startswith(want + "-")]
    if variants:
        return sorted(variants, key=len)[0]
    return None


def download_sub(url: str, lang: str, workdir: str) -> str:
    """Download the manual subtitle for `lang`; return the local file path."""
    outtmpl = os.path.join(workdir, "sub.%(ext)s")
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writesubtitles": True,        # manual subs only
        "writeautomaticsub": False,    # never auto-captions
        "subtitleslangs": [lang],
        "subtitlesformat": "vtt/srt/best",
        "outtmpl": outtmpl,
    }
    YoutubeDL = _load_ydl()
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    matches = glob.glob(os.path.join(workdir, "sub.*"))
    if not matches:
        raise FileNotFoundError("yt-dlp reported success but wrote no subtitle file")
    return matches[0]


_TIMESTAMP_RE = re.compile(r"^\d{1,2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*")
_CUE_NUMBER_RE = re.compile(r"^\d+$")
_TAG_RE = re.compile(r"<[^>]+>")  # inline VTT tags like <00:00:01.000> or <c>


def subtitle_to_text(path: str) -> str:
    """Convert a VTT or SRT file to plain text.

    Strips the WEBVTT header, cue numbers, timestamp lines, and inline tags;
    joins cue text with newlines; collapses consecutive duplicate lines.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        raw_lines = fh.read().splitlines()

    lines: list[str] = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.upper().startswith("WEBVTT"):
            continue
        if stripped.startswith(("NOTE", "STYLE", "Kind:", "Language:")):
            continue
        if _TIMESTAMP_RE.match(stripped):
            continue
        if _CUE_NUMBER_RE.match(stripped):
            continue
        text = _TAG_RE.sub("", stripped).strip()
        if text:
            lines.append(text)

    # Collapse consecutive duplicates (common in rolling-caption VTT).
    deduped: list[str] = []
    for line in lines:
        if not deduped or deduped[-1] != line:
            deduped.append(line)
    return "\n".join(deduped) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract a YouTube manual subtitle and convert it to plain text.",
        epilog="Exits non-zero if no manual subtitle exists in the requested language.",
    )
    parser.add_argument("source", help="YouTube URL or bare video ID")
    parser.add_argument("out", help="output .txt path")
    parser.add_argument(
        "--lang", default="en",
        help="target subtitle language code (default: en; matches en-US/en-GB/en-orig)",
    )
    args = parser.parse_args()

    url = normalize_id(args.source)

    try:
        available = list_manual_sub_langs(url)
    except Exception as exc:  # network / extraction failure
        sys.stderr.write(f"error: could not probe subtitles for {url!r}: {exc}\n")
        return 1

    if not available:
        sys.stderr.write(
            "no MANUAL subtitle of any language exists for this video.\n"
            "Fall back to the audio pipeline: download audio with yt-dlp, then "
            "transcribe locally (see SKILL.md §B).\n"
        )
        return 3

    lang = pick_lang(available, args.lang)
    if lang is None:
        sys.stderr.write(
            f"no MANUAL subtitle in language {args.lang!r}. "
            f"Available manual subs: {', '.join(available)}.\n"
            "Either pass --lang for one of the above, or fall back to the audio "
            "pipeline (see SKILL.md §B).\n"
        )
        return 3

    with tempfile.TemporaryDirectory() as workdir:
        try:
            sub_path = download_sub(url, lang, workdir)
        except Exception as exc:
            sys.stderr.write(f"error: failed to download subtitle ({lang}): {exc}\n")
            return 1
        try:
            text = subtitle_to_text(sub_path)
        except Exception as exc:
            sys.stderr.write(f"error: failed to parse subtitle file: {exc}\n")
            return 1

    if not text.strip():
        sys.stderr.write("error: extracted subtitle was empty after cleanup.\n")
        return 1

    try:
        out_dir = os.path.dirname(os.path.abspath(args.out))
        os.makedirs(out_dir, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError as exc:
        sys.stderr.write(f"error: could not write {args.out!r}: {exc}\n")
        return 1

    sys.stderr.write(f"wrote manual subtitle ({lang}) to {args.out}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
