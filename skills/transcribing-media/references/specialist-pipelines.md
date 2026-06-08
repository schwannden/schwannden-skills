# Language specialist pipelines + eval-against-gold

## Table of contents
- [When to reach for a specialist](#when-to-reach-for-a-specialist)
- [English specialist: parakeet-mlx (Apple Silicon)](#english-specialist-parakeet-mlx-apple-silicon)
- [The parakeet v2-vs-v3 trap](#the-parakeet-v2-vs-v3-trap)
- [English alternative: mlx-whisper large-v3-turbo](#english-alternative-mlx-whisper-large-v3-turbo)
- [Mandarin / Chinese specialist: mlx-qwen3-asr](#mandarin--chinese-specialist-mlx-qwen3-asr)
- [Mandarin critical knobs](#mandarin-critical-knobs)
- [Simplified to Traditional with opencc](#simplified-to-traditional-with-opencc)
- [Eval against a gold transcript](#eval-against-a-gold-transcript)

These are **opt-in upgrades** over the multilingual default in `engines.md`.
Use them when the language is known and accuracy matters.

## When to reach for a specialist

The multilingual whisper default is solid. Switch to a specialist when:

- The language is known and fixed (a whole batch is English, or all Mandarin).
- Accuracy on proper nouns or idioms matters.
- You are on hardware the specialist targets (parakeet/qwen3 specialists below
  target Apple Silicon / MLX).

## English specialist: parakeet-mlx (Apple Silicon)

`parakeet-mlx` runs NVIDIA Parakeet models under MLX. It is very fast and
accurate on clean English speech.

```bash
uvx --from parakeet-mlx parakeet-mlx audio.mp3 \
  --model mlx-community/parakeet-tdt-0.6b-v2 \
  --output-dir out_dir \
  --output-format txt \
  --chunk-duration 120 \
  --overlap-duration 15
```

`--chunk-duration` / `--overlap-duration` window long files so context is not
lost at chunk boundaries; the overlap is de-duplicated on stitch.

## The parakeet v2-vs-v3 trap

**This is the single most important gotcha for this engine.** The
`parakeet-mlx` CLI's **default model is v3 (multilingual)**, which is several WER
points worse on English than the English-tuned **v2**. The default *looks* like
it works — output is fluent — but it is quietly less accurate.

**Always pass `--model mlx-community/parakeet-tdt-0.6b-v2` explicitly** for
English work. Do not rely on the default. The first symptom of getting this
wrong is rare-name misspellings (an uncommon surname coming out a letter or two
off) and a measurably higher WER on an eval.

## English alternative: mlx-whisper large-v3-turbo

When proper nouns matter more than raw speed, `mlx-whisper large-v3-turbo` is
the proper-noun-friendly alternative — comparable overall WER to parakeet v2 but
better on rare names.

```bash
uv run --with mlx-whisper python -m mlx_whisper \
  --model mlx-community/whisper-large-v3-turbo \
  --language en \
  --output-dir out_dir --output-format txt \
  audio.mp3
```

**Warning on `initial_prompt`:** priming whisper with a long `initial_prompt`
(e.g. a big glossary) gives at best a marginal named-entity gain and risks
**hallucination loops** — the model starts emitting the prompt text or repeats
phrases. Keep any prompt short (≤ ~200 tokens) or drop it entirely.

## Mandarin / Chinese specialist: mlx-qwen3-asr

`mlx-qwen3-asr` runs Qwen3-ASR under MLX and handles literary/idiomatic Chinese
well.

```bash
mlx-qwen3-asr audio.mp3 \
  --model Qwen/Qwen3-ASR-1.7B \
  --dtype float16 \
  --language Chinese \
  --context "Acme Corp, Dr. Smith, Project Aurora" \
  -f txt -o out_dir \
  --no-progress
```

(Install with `uvx --from mlx-qwen3-asr mlx-qwen3-asr ...` or via the `uv` skill.)

## Mandarin critical knobs

- **`--model Qwen/Qwen3-ASR-1.7B`** — use the 1.7B model. The 0.6B variant
  mangles idioms and literary Chinese; the 1.7B handles them.
- **`--language Chinese`** — forces language ID. Without it, mid-utterance
  English code-switching can flip the recognizer's language mid-stream. Forcing
  Chinese keeps the whole utterance in the right script.
- **`--context "<glossary>"`** — the **single highest-leverage flag**. Pass a
  short comma-separated list of the proper nouns expected in the audio (people,
  organizations, place names, domain terms). It recovers names the model would
  otherwise mishear. Use a glossary tailored to the specific recording, e.g.
  `--context "Acme Corp, Dr. Smith, Project Aurora"`.
- **Do NOT enable speculative `--draft-model` decoding.** It regressed mid-batch
  in production (quality and speed both degraded partway through a long run).
  Stick with the vanilla 1.7B model. Re-test speculative decoding in isolation
  before ever re-enabling it on a real batch.

## Simplified to Traditional with opencc

Qwen3-ASR emits Simplified Chinese. To convert to Traditional (Taiwan style,
including phrase-level conversion of vocabulary differences), post-process with
`opencc`:

```bash
opencc -c s2twp.json -i out_dir/audio.txt -o final.txt
```

`s2twp.json` is the Simplified→Traditional-with-Taiwan-phrases config. Use
`s2t.json` for a plain script-only conversion without the regional phrase
substitutions.

## Eval against a gold transcript

When a known-good (gold) transcript exists, **measure** instead of eyeballing.
Compute three numbers against the gold:

1. **WER (word error rate)** — for space-delimited languages like English.
   Edit distance over word tokens ÷ gold word count.
2. **CER (character error rate)** — the right metric for Chinese (no word
   boundaries). Edit distance over characters ÷ gold character count.
3. **Named-entity recall** — over a proper-noun glossary, the fraction of gold
   entities that appear in the candidate. This is what actually matters for
   readability; a transcript can have low WER but still drop the one name a
   reader cares about.

Procedure:

1. Normalize both transcripts the same way: lowercase (for English), strip
   punctuation, collapse whitespace. For Chinese, normalize full/half-width and
   drop spaces so CER is computed over characters.
2. Tokenize — words for WER, characters for CER.
3. Compute Levenshtein edit distance over the token sequence; divide by the gold
   token count to get the rate.
4. For NE recall, check each glossary entity for presence in the candidate;
   recall = found ÷ total.
5. Report all three. A lower WER/CER with **lower** NE recall is usually the
   wrong tradeoff for human-readable transcripts — weight NE recall heavily.

A minimal Python sketch (run with the `uv` skill,
`uv run --with rapidfuzz python -`):

```python
from rapidfuzz.distance import Levenshtein

def wer(gold, cand):
    g, c = gold.lower().split(), cand.lower().split()
    return Levenshtein.distance(g, c) / max(len(g), 1)

def cer(gold, cand):
    g = "".join(gold.split()); c = "".join(cand.split())
    return Levenshtein.distance(g, c) / max(len(g), 1)

def ne_recall(gold, cand, glossary):
    found = sum(1 for e in glossary if e in cand)
    return found / max(len(glossary), 1)
```

Use the eval to compare engines on the **same** audio before committing to a
batch: pick the engine with acceptable WER/CER and the best NE recall.
