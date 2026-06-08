#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["faster-whisper"]
# ///
"""Resumable batch transcription driver.

RUN THIS (do not just read it):

    uv run scripts/transcribe_batch.py <inputs...|dir> --out <dir> \\
        [--engine auto|mlx-whisper|faster-whisper] [--lang en] [--model NAME]

For each input audio/video file it:
  1. computes an output .txt path under <dir>,
  2. SKIPS the file if that output already exists and is non-empty (resumable),
  3. transcribes with the chosen engine:
       - faster-whisper: via the faster_whisper Python API,
       - mlx-whisper: by shelling out to the mlx-whisper CLI,
  4. appends `(file, audio_sec, wall_sec, rtf)` to <dir>/ledger.tsv,
  5. on a per-file error, logs it and CONTINUES (one bad file never aborts the
     whole batch); the process exits non-zero if any file failed.

`--engine auto` reuses the detection logic in detect_backend.py (imported, not
duplicated). The mlx-whisper path requires the `mlx-whisper` CLI on PATH (e.g.
installed via `uv tool install mlx-whisper`); the faster-whisper path resolves
its dependency automatically under `uv run`.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# Reuse the shared detection logic instead of duplicating it.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detect_backend import detect_backend  # noqa: E402

AUDIO_EXTS = {
    ".mp3", ".m4a", ".wav", ".flac", ".opus", ".ogg", ".aac",
    ".mp4", ".mov", ".mkv", ".webm",
}


def resolve_engine(name: str) -> str:
    """Map an --engine choice to a concrete engine key.

    'auto' delegates to detect_backend(); 'faster-whisper' covers both the CUDA
    and CPU variants (device is chosen below).
    """
    if name == "auto":
        key = detect_backend().key
        return "mlx-whisper" if key == "mlx-whisper" else "faster-whisper"
    return name


def faster_whisper_device() -> tuple[str, str]:
    """Return (device, compute_type) appropriate for this machine."""
    if detect_backend().key == "faster-whisper-cuda":
        return "cuda", "float16"
    return "cpu", "int8"


def gather_inputs(inputs: list[str]) -> list[Path]:
    """Expand directories into their audio/video files; keep explicit files."""
    files: list[Path] = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            files.extend(
                sorted(c for c in p.iterdir() if c.suffix.lower() in AUDIO_EXTS)
            )
        elif p.is_file():
            files.append(p)
        else:
            sys.stderr.write(f"warning: skipping missing input {item!r}\n")
    return files


def audio_duration_sec(path: Path) -> float | None:
    """Best-effort media duration via ffprobe; None if unavailable."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(path),
            ],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return None


def transcribe_faster_whisper(path: Path, out_txt: Path, lang: str | None,
                              model_name: str) -> None:
    """Transcribe with the faster_whisper Python API."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "faster-whisper unavailable; run this script with `uv run`"
        ) from exc

    device, compute = faster_whisper_device()
    model = WhisperModel(model_name, device=device, compute_type=compute)
    segments, _info = model.transcribe(str(path), language=lang)
    text = "\n".join(seg.text.strip() for seg in segments)
    out_txt.write_text(text + "\n", encoding="utf-8")


def transcribe_mlx_whisper(path: Path, out_txt: Path, lang: str | None,
                           model_name: str) -> None:
    """Transcribe by shelling out to the mlx-whisper CLI."""
    cmd = [
        "mlx_whisper",
        "--model", model_name,
        "--output-dir", str(out_txt.parent),
        "--output-format", "txt",
    ]
    if lang:
        cmd += ["--language", lang]
    cmd.append(str(path))

    # The CLI may be exposed as `mlx_whisper` or `python -m mlx_whisper`.
    import shutil
    if shutil.which("mlx_whisper") is None:
        cmd = [sys.executable, "-m", "mlx_whisper"] + cmd[1:]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"mlx-whisper failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    # mlx-whisper names the output after the input stem; rename to out_txt.
    produced = out_txt.parent / (path.stem + ".txt")
    if produced != out_txt and produced.exists():
        produced.replace(out_txt)


def default_model(engine: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    if engine == "mlx-whisper":
        return "mlx-community/whisper-large-v3-turbo"
    return "large-v3"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resumable batch transcription driver."
    )
    parser.add_argument("inputs", nargs="+", help="audio/video files or a directory")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument(
        "--engine", default="auto",
        choices=["auto", "mlx-whisper", "faster-whisper"],
        help="engine to use (auto = detect this machine; default: auto)",
    )
    parser.add_argument("--lang", default=None, help="force language code (e.g. en)")
    parser.add_argument("--model", default=None, help="override model name")
    args = parser.parse_args()

    engine = resolve_engine(args.engine)
    model_name = default_model(engine, args.model)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = out_dir / "ledger.tsv"
    if not ledger.exists():
        ledger.write_text("file\taudio_sec\twall_sec\trtf\n", encoding="utf-8")

    files = gather_inputs(args.inputs)
    if not files:
        sys.stderr.write("error: no audio/video inputs found.\n")
        return 1

    sys.stderr.write(
        f"engine={engine} model={model_name} files={len(files)} out={out_dir}\n"
    )

    failures = 0
    for path in files:
        out_txt = out_dir / (path.stem + ".txt")
        if out_txt.exists() and out_txt.stat().st_size > 0:
            sys.stderr.write(f"skip (resumable): {path.name}\n")
            continue

        audio_sec = audio_duration_sec(path)
        start = time.monotonic()
        try:
            if engine == "mlx-whisper":
                transcribe_mlx_whisper(path, out_txt, args.lang, model_name)
            else:
                transcribe_faster_whisper(path, out_txt, args.lang, model_name)
        except Exception as exc:
            failures += 1
            sys.stderr.write(f"FAILED {path.name}: {exc}\n")
            # Remove any partial output so the file is retried next run.
            if out_txt.exists() and out_txt.stat().st_size == 0:
                out_txt.unlink()
            continue

        wall = time.monotonic() - start
        rtf = (wall / audio_sec) if audio_sec else float("nan")
        with ledger.open("a", encoding="utf-8") as fh:
            a = f"{audio_sec:.1f}" if audio_sec else "NA"
            fh.write(f"{path.name}\t{a}\t{wall:.1f}\t{rtf:.4f}\n")
        sys.stderr.write(f"done: {path.name} ({wall:.1f}s, rtf={rtf:.4f})\n")

    if failures:
        sys.stderr.write(f"\n{failures} file(s) failed; see messages above.\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
