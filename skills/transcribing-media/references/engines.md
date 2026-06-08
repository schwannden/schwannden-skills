# Transcription engines — platform matrix, installs, commands, throughput

## Table of contents
- [Choosing an engine](#choosing-an-engine)
- [The machine-build matrix](#the-machine-build-matrix)
- [Apple Silicon: mlx-whisper](#apple-silicon-mlx-whisper)
- [NVIDIA GPU: faster-whisper (CUDA)](#nvidia-gpu-faster-whisper-cuda)
- [CPU / other: faster-whisper (int8) or whisper.cpp](#cpu--other-faster-whisper-int8-or-whispercpp)
- [whisper.cpp as a portable fallback](#whispercpp-as-a-portable-fallback)
- [Models](#models)
- [Throughput notes](#throughput-notes)
- [Running everything through uv](#running-everything-through-uv)

This file is the **machine-build layer**: which whisper runtime to use on which
hardware, how to install it, the verified canonical command, and observed
throughput. The multilingual default lives here; language-specific upgrades live
in `specialist-pipelines.md`.

## Choosing an engine

Run the bundled detector — it inspects OS, architecture, and GPU and prints a
ready-to-run command:

```bash
uv run scripts/detect_backend.py path/to/audio.mp3
```

The detector is pure stdlib, so `python3 scripts/detect_backend.py ...` works
too. `scripts/transcribe_batch.py --engine auto` calls the same detection logic.

## The machine-build matrix

| Build | Multilingual default | Runtime | Why |
|---|---|---|---|
| Apple Silicon (arm64 macOS) | `mlx-whisper` (`large-v3-turbo`) | MLX / Metal | MLX uses the Apple GPU + unified memory; turbo is fast and accurate |
| NVIDIA GPU | `faster-whisper` `--device cuda` | CTranslate2 | CTranslate2 CUDA kernels are the fastest portable GPU path |
| CPU / other | `faster-whisper` `--device cpu --compute-type int8` | CPU | int8 quantization keeps CPU transcription tractable |

`whisper.cpp` is a good portable alternative on any of these (especially when
you want a single self-contained binary).

## Apple Silicon: mlx-whisper

Install / run via uv (no global install needed):

```bash
uv run --with mlx-whisper python -m mlx_whisper \
  --model mlx-community/whisper-large-v3-turbo \
  --output-dir out_dir \
  --output-format txt \
  audio.mp3
```

`mlx-whisper` downloads MLX-format models from the model hub on first use and
caches them. `large-v3-turbo` is the recommended multilingual default: close to
`large-v3` accuracy at a fraction of the time.

For English-only or Mandarin work on Apple Silicon, see the specialists in
`specialist-pipelines.md` (`parakeet-mlx`, `mlx-qwen3-asr`).

## NVIDIA GPU: faster-whisper (CUDA)

`faster-whisper` is a CTranslate2 reimplementation of whisper. Use the Python
API (what `transcribe_batch.py` uses) or a thin CLI wrapper:

```python
# uv run --with faster-whisper python -
from faster_whisper import WhisperModel
model = WhisperModel("large-v3", device="cuda", compute_type="float16")
segments, info = model.transcribe("audio.mp3", language="en")
text = "\n".join(s.text.strip() for s in segments)
```

`compute_type="float16"` is the GPU default; drop to `int8_float16` if VRAM is
tight. Requires the CUDA + cuDNN runtime libraries that CTranslate2 expects.

## CPU / other: faster-whisper (int8) or whisper.cpp

```python
# uv run --with faster-whisper python -
from faster_whisper import WhisperModel
model = WhisperModel("large-v3", device="cpu", compute_type="int8")
segments, info = model.transcribe("audio.mp3")
```

int8 quantization makes CPU transcription usable; expect it to be much slower
than any GPU path. For long files on CPU, prefer a smaller model (`small`,
`medium`) or `whisper.cpp` with a quantized GGUF model.

## whisper.cpp as a portable fallback

`whisper.cpp` runs a single C++ binary against a quantized GGUF model and builds
with CUDA, Metal, or plain CPU. It is the most portable option when you cannot
install a Python ML stack:

```bash
# After building whisper.cpp and downloading a ggml model:
./main -m models/ggml-large-v3-turbo.bin -f audio.wav -otxt -of out
```

It expects 16 kHz mono WAV; convert first with ffmpeg if needed
(`ffmpeg -i in.mp3 -ar 16000 -ac 1 out.wav`).

## Models

| Model | Use | Notes |
|---|---|---|
| `large-v3-turbo` | Default multilingual | Best speed/accuracy tradeoff |
| `large-v3` | Max accuracy multilingual | Slower; use when accuracy is paramount |
| `medium` / `small` | CPU or low-memory | Lower accuracy; faster |

Models download from the hub on first use and are cached. The **first** run of
any new model pays a multi-GB download cost — see the pre-flight checklist about
cold-run timing.

## Throughput notes

Real-time factor (RTF) = wall-clock seconds ÷ audio seconds; lower is faster.
Figures below were **observed on Apple Silicon** with warm model caches and are
indicative only — your hardware, model, and audio will differ.

| Engine (warm cache) | Observed RTF | Rough speedup |
|---|---|---|
| `parakeet-mlx` v2 (English) | ~0.02 | ~50× real-time |
| `mlx-qwen3-asr` 1.7B (Mandarin) | ~0.13 | ~8× real-time |

Always re-measure on your own machine after the model is cached; cold runs
include the download and badly overstate RTF.

## Running everything through uv

Use the built-in `uv` skill. `uv run --with <pkg> ...` resolves the named
package into an ephemeral environment without touching your global Python.
`uvx <tool>` runs a CLI tool the same way. The bundled scripts declare their
dependencies via PEP 723 inline metadata, so `uv run scripts/<name>.py` just
works. Never `pip install` these globally.
