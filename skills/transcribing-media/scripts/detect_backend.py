#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Detect this machine's build and recommend a transcription engine.

RUN THIS (do not just read it):

    uv run scripts/detect_backend.py [path/to/audio.mp3]
    # or, since it is pure stdlib:
    python3 scripts/detect_backend.py [path/to/audio.mp3]

It inspects the OS, CPU architecture, and whether an NVIDIA GPU is present, then
prints the recommended engine, an install hint, and a ready-to-run command
template for the given audio file (a placeholder is used if none is given).

This module also exposes `detect_backend()` and `recommend()` so the batch
driver (transcribe_batch.py) can reuse the exact same logic without duplicating
it. No third-party dependencies, so it always runs.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class Backend:
    """A recommended transcription backend for the current machine."""

    key: str           # "mlx-whisper" | "faster-whisper-cuda" | "faster-whisper-cpu"
    label: str         # human-readable description
    install_hint: str  # how to make it available
    runtime: str       # "MLX/Metal" | "CTranslate2 CUDA" | "CTranslate2 CPU"


def has_nvidia_gpu() -> bool:
    """True if an NVIDIA GPU appears usable (nvidia-smi present and succeeds)."""
    if shutil.which("nvidia-smi") is None:
        return False
    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and "GPU" in result.stdout


def is_apple_silicon() -> bool:
    """True on arm64 macOS (Apple Silicon)."""
    return platform.system() == "Darwin" and platform.machine().lower() in {
        "arm64",
        "aarch64",
    }


def detect_backend() -> Backend:
    """Pick the best multilingual default engine for THIS machine."""
    if is_apple_silicon():
        return Backend(
            key="mlx-whisper",
            label="mlx-whisper (large-v3-turbo) on Apple Silicon",
            install_hint="uv run --with mlx-whisper python -m mlx_whisper ...",
            runtime="MLX/Metal",
        )
    if has_nvidia_gpu():
        return Backend(
            key="faster-whisper-cuda",
            label="faster-whisper on NVIDIA GPU (CUDA)",
            install_hint="uv run --with faster-whisper python ...",
            runtime="CTranslate2 CUDA",
        )
    return Backend(
        key="faster-whisper-cpu",
        label="faster-whisper on CPU (int8)",
        install_hint="uv run --with faster-whisper python ...",
        runtime="CTranslate2 CPU",
    )


def recommend(audio: str) -> str:
    """Return a ready-to-run command template for `audio` on this machine."""
    backend = detect_backend()
    if backend.key == "mlx-whisper":
        return (
            "uv run --with mlx-whisper python -m mlx_whisper \\\n"
            "  --model mlx-community/whisper-large-v3-turbo \\\n"
            "  --output-dir out_dir --output-format txt \\\n"
            f"  {audio}"
        )
    device = "cuda" if backend.key == "faster-whisper-cuda" else "cpu"
    compute = "float16" if device == "cuda" else "int8"
    return (
        "uv run --with faster-whisper python - <<'PY'\n"
        "from faster_whisper import WhisperModel\n"
        f'model = WhisperModel("large-v3", device="{device}", '
        f'compute_type="{compute}")\n'
        f'segments, info = model.transcribe("{audio}")\n'
        'text = "\\n".join(s.text.strip() for s in segments)\n'
        'open("out.txt", "w", encoding="utf-8").write(text + "\\n")\n'
        "PY"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect machine build and recommend a transcription engine."
    )
    parser.add_argument(
        "audio",
        nargs="?",
        default="path/to/audio.mp3",
        help="audio file to template a command for (optional)",
    )
    args = parser.parse_args()

    try:
        backend = detect_backend()
    except Exception as exc:  # defensive: detection should never hard-fail
        sys.stderr.write(f"error: backend detection failed: {exc}\n")
        return 1

    print(f"OS / arch     : {platform.system()} / {platform.machine()}")
    print(f"Recommended   : {backend.label}")
    print(f"Runtime       : {backend.runtime}")
    print(f"Install / run : {backend.install_hint}")
    print()
    print("Ready-to-run command:")
    print(recommend(args.audio))
    print()
    print(
        "For a language specialist (English parakeet-mlx, Mandarin "
        "mlx-qwen3-asr), see references/specialist-pipelines.md."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
