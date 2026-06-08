---
name: transcribing-media
description: >
  Transcribe audio, video, or YouTube content to text using the best LOCAL pipeline for the
  user's machine. Use when: (1) the user shares a YouTube URL or video ID and wants to read the
  spoken content, (2) the user provides a local audio file (.mp3/.m4a/.wav/.flac/.opus) or video
  file (.mp4/.mov/.mkv/.webm) and wants the speech as text, (3) the user says "transcribe", "pull
  the transcript", "convert audio to text", "get captions/subtitles", or "speech to text". Defaults
  to a multilingual whisper engine and offers opt-in English and Mandarin/Chinese specialists.
  Keywords: transcribe, transcription, audio, video, YouTube, subtitles, captions, speech-to-text,
  ASR, whisper, mlx-whisper, faster-whisper, whisper.cpp, parakeet, Qwen3-ASR, Mandarin, Chinese,
  opencc, local model, Apple Silicon, CUDA, GPU, WER, CER.
---

# Transcribing media

Route any audio / video / YouTube input to the best **local** transcription
pipeline for the machine you are on. The default path is a multilingual whisper
engine chosen by hardware; language **specialists** are opt-in upgrades.

Two principles dominate every decision:

1. **Subtitle-first.** If a YouTube video already has a human-authored manual
   subtitle, extracting it is near-instant and near-zero error — it beats any
   audio pipeline. Always probe for one before downloading audio.
2. **Match the engine to the machine.** The right whisper runtime depends on
   the build (Apple Silicon / NVIDIA GPU / CPU). Detect, then transcribe.

This SKILL.md is the **router**. Deep operational detail lives in two reference
files (read the one your task needs):

- `references/engines.md` — platform→engine matrix, installs, canonical
  commands, throughput.
- `references/specialist-pipelines.md` — English + Mandarin specialist upgrades
  and the eval-against-gold procedure.

The bundled `scripts/` are **runnable**. Run them with the built-in `uv` skill
(`uv run <script>`) so PEP 723 inline dependencies resolve into a throwaway
environment — never `pip install` globally. `detect_backend.py` is pure stdlib
and runs with plain `python3` too.

## Decision tree

```
<source>
  ├─ YouTube URL or video ID? ──────────────► §A YouTube path
  └─ local audio / video file? ─────────────► §B local-file path
```

```
§A YouTube
  1. Probe for a MANUAL subtitle in the target language.
  2. Manual sub exists? ──yes──► extract it (scripts/yt_subs_to_txt.py). DONE.
                         ──no───► download audio with yt-dlp, fall through to §B.

§B local file
  1. scripts/detect_backend.py → recommended engine for THIS machine.
  2. Need a language specialist? ──► references/specialist-pipelines.md
                                ──► else run the multilingual default.
```

## §A YouTube path (subtitle-first)

```bash
# 1) Probe manual subtitles (NOT auto-captions).
uvx yt-dlp --list-subs --skip-download "<url>"
# The "Available subtitles" section lists human-authored subs.
# "Available automatic captions" is YouTube's own ASR — last resort only.

# 2) If a manual sub exists in the target language, extract it:
uv run scripts/yt_subs_to_txt.py "<url-or-id>" out.txt --lang en
# Near-instant; downloads the manual VTT/SRT and converts to plain text
# (cue text joined by newlines; timestamps and cue numbers stripped;
#  duplicate consecutive lines collapsed). Exits non-zero if no manual
# sub exists — that is your signal to fall back to audio.

# 3) If no manual sub, download audio and fall through to §B:
uvx yt-dlp -f "bestaudio[ext=m4a]/bestaudio" \
  --extract-audio --audio-format mp3 --audio-quality 0 \
  -o "%(title)s.%(ext)s" "<url>"
```

Why subtitle-first: a human-authored manual sub is effectively a gold
transcript — 0% word error against the audio it was written for. No local model
beats it, and it costs seconds. Only fall through to audio when no manual sub
exists. Auto-captions are machine ASR of unknown quality; prefer your own local
pipeline over them.

Quality caveat: manual subs can carry isolated uploader typos (especially in
proper nouns). After extraction, sweep a short proper-noun glossary with a
Levenshtein-1 check and fix obvious misspellings. Do **not** strip
`Speaker N:` prefixes — for many uploaders they are part of the canonical
format.

## §B Local-file path (detect → transcribe)

```bash
# 1) Let the machine pick its engine and print a ready-to-run command:
uv run scripts/detect_backend.py path/to/audio.mp3
```

The script reports the recommended engine, an install hint, and a command
template. The multilingual default by build:

| Build | Multilingual default | Runtime |
|---|---|---|
| Apple Silicon (arm64 macOS) | `mlx-whisper` (large-v3-turbo) | MLX / Metal |
| NVIDIA GPU | `faster-whisper` `--device cuda` (or whisper.cpp CUDA) | CTranslate2 |
| CPU / other | `faster-whisper` `--device cpu --compute-type int8` (or whisper.cpp) | CPU |

See `references/engines.md` for install commands, exact canonical invocations,
and observed throughput.

For a real batch, prefer the resumable driver over a hand-rolled loop:

```bash
uv run scripts/transcribe_batch.py path/to/audio_dir --out out_dir --engine auto
```

It detects the engine (`auto`), skips inputs whose output already exists
(resumable), records `(file, audio_sec, wall_sec, rtf)` to `<out>/ledger.tsv`,
and survives per-file errors without aborting the batch.

## Language specialists (opt-in upgrades)

The multilingual default is good. For higher accuracy in a known language, read
`references/specialist-pipelines.md` and use:

- **English on Apple Silicon → `parakeet-mlx`.** Trap: the CLI default model is
  **v3 (multilingual)**, several WER points worse on English than **v2**. Always
  pass `--model mlx-community/parakeet-tdt-0.6b-v2` explicitly. If proper nouns
  matter more than raw speed, `mlx-whisper large-v3-turbo` is the
  proper-noun-friendly alternative — but keep any `initial_prompt` short, since
  a long prompt can trigger hallucination loops.
- **Mandarin / Chinese → `mlx-qwen3-asr` (Qwen3-ASR 1.7B).** The 1.7B model
  handles literary/idiomatic Chinese; the 0.6B mangles idioms. Pass
  `--language Chinese` to force language ID across English code-switching, and
  use `--context "<glossary>"` for proper nouns (the single highest-leverage
  flag). Do **not** enable speculative `--draft-model` decoding — it regressed
  mid-batch in production. Then convert Simplified → Traditional with
  `opencc -c s2twp.json`.

## Pre-flight checklist (run before EVERY batch)

1. **Kill competing ASR apps.** `pgrep -if "whisper|asr"` — anything live
   saturates the GPU and spikes real-time-factor; pause or quit it.
2. **Stay sequential on a single-GPU machine.** Two ASR jobs halve each other.
   One transcription at a time.
3. **Cold-run timing lies.** The first run downloads multi-GB models from the
   hub; that time is counted in the RTF. Re-measure warm.
4. **Resumability.** Any batch run must skip inputs whose output already
   exists. `scripts/transcribe_batch.py` does this for you.

## Cross-cutting failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Cold-run RTF terrible | Model download counted in the timing | Re-measure after models are cached |
| RTF spikes 10×+ mid-batch | A competing ASR app on the GPU | Pre-flight `pgrep -if "whisper\|asr"` |
| Parallel jobs each run at half speed | Single GPU saturated | Stay sequential |
| English: rare name misspelled (e.g. `Walke`) | parakeet **v3** default + no priming | Pass `--model ...parakeet-tdt-0.6b-v2`; or use mlx-whisper turbo |
| Mandarin: proper noun mangled | Missing `--context` | Add the entity to the context glossary string |
| Mandarin output is Simplified, not Traditional | Forgot the opencc post-process | Pipe through `opencc -c s2twp.json` |
| Mandarin: quality degrades mid-batch | Speculative `--draft-model` decoding regressed | Disable it; use vanilla 1.7B |
| Long whisper `initial_prompt` → repeated/hallucinated text | Prompt too long or has repeated terms | Trim to ≤ ~200 tokens, or drop the prompt |
| YouTube sub has an isolated typo | Uploader artifact | Levenshtein-1 glossary sweep + targeted fix |
| `Speaker N:` prefix in a YouTube sub | Uploader convention (not always present) | Keep it — it is part of the canonical format |

## Verifying transcription quality

When a known-good reference (gold) transcript exists, measure rather than
eyeball: compute **WER** (word error rate), **CER** (character error rate, the
right metric for Chinese), and **named-entity recall** over a proper-noun
glossary. The procedure is in `references/specialist-pipelines.md`. Without a
gold reference, spot-check 3–5 outputs (first ~400 chars plus a random middle
slice) for hallucinations, length sanity, and idiom corruption.
