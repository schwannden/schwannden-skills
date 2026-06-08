---
name: comparing-model-variants
description: >
  Use when comparing local ML model variants (which Whisper/Parakeet/Qwen/Llama,
  which quantization, fp16 vs int8), tuning inference parameters (chunk size,
  beam width, dtype, speculative decoding, context priming), or selecting between
  candidate local-inference pipeline architectures. Triggers: "which model is best",
  "find the optimal config", "tune the pipeline", "compare these inference methods",
  "is X faster than Y", "speed vs accuracy tradeoff", any question requiring
  side-by-side empirical comparison on local hardware. Scope: LOCAL models on
  LOCAL hardware only — does not apply to API/cloud benchmarking.
---

# Comparing Model Variants

Disciplined experimental loop for picking the right local model + inference config on a specific machine. Inspired by Karpathy-style disciplined experimentation and refined across repeated local-inference tuning sessions.

**Core principle:** fix the budget, optimize one number, change one knob at a time, log every run to an append-only TSV, never tune by ear.

## When to use

- Choosing between local model variants (Whisper-large vs Parakeet-TDT-v2 vs v3 vs distil; Qwen3-30B vs Llama-3.3-70B at q4 vs q5)
- Tuning a single pipeline (chunk duration, beam size, initial_prompt content, VAD settings, dtype)
- Comparing pipeline architectures (one-stage vs two-stage; ASR alone vs ASR + LLM proofread)
- Verifying a config still works after a library upgrade
- Predicting batch throughput before committing to a long run

## When NOT to use

- One-off bug fix or refactor (not research)
- API/cloud model selection (different cost model, different bottlenecks)
- Picking a research direction or feature design (use brainstorming)
- "Is this faster than my Python version" benchmarks of non-ML code

## The Iron Law

**Local hardware is the boundary condition, not an afterthought.** Every claim is "X is best *on this machine*". Numbers from other machines, other batch sizes, or other thermal states are not yours.

### Rules (non-negotiable)

1. **Fix the eval set.** Pick a small, representative input (~5–30 min of audio, ~10K tokens of test prompts, etc.) and a known gold/reference. Never modify the eval mid-experiment. If gold is unavailable, hand-build ~500 words/tokens and freeze them.
2. **One number to optimize.** Pick *one* primary metric (WER, perplexity, accuracy, RTF). Secondary metrics (memory, latency) are *soft constraints*, not co-optimized goals. Numbers on a screen beat hand-waved "better."
3. **Baseline first, always.** Run #1 is always the unmodified vanilla default. Every later number is delta-from-baseline. Without a baseline you don't know if you're "improving."
4. **One knob per run.** Never change two things at once. If you do, you cannot attribute the delta.
5. **Append-only TSV ledger.** Every run gets a row in `results.tsv`. No re-deriving. No "I'll remember." Schema below.
6. **Simplicity is the tiebreaker.** A 0.5% improvement that adds 50 lines of pipeline glue is not worth it. Improvements from *deleting* a flag are pure wins.
7. **Don't tune by ear.** "It sounded better" is not a number. If you can't grep the metric you used, you didn't measure.
8. **Cold-run RTF is a lie.** First run includes multi-GB model-hub download. Re-measure after the cache is warm. Always.

## The loop

```
seed eval set  →  run baseline  →  log to TSV  →
  ┌── change ONE knob ────────────────────────┐
  ▼                                            │
  run on same eval  →  log to TSV  →  decide ─┘
       (keep / revert / advance)
```

Stop when:
- Two successive changes give < 0.5% absolute improvement in your primary metric, OR
- You hit a domain-specific quality floor (e.g., WER < 5%), OR
- Soft constraints break (memory exceeded, wall too slow for batch)

## Recommended layout

```
<project>/_experiments/<topic>/
├── eval/                       # Frozen gold inputs + references
│   ├── input.<ext>
│   └── gold.txt
├── results.tsv                 # Append-only ledger
├── run_NN_<short-name>.txt     # Per-run outputs (kept for diffing)
├── glossary.txt                # NE-recall vocabulary (if relevant)
└── notes.md                    # Optional: per-run paragraph if surprised
```

`results.tsv` schema (use real domain metrics):

```
run_id	config	primary_metric	secondary	audio_sec	wall_sec	rtf	notes
01	parakeet-tdt-0.6b-v3 cold defaults	0.1227	0.0890	4732	90	0.019	multilingual; worse on English
02	parakeet-tdt-0.6b-v2 cold defaults	0.0796	0.0509	4732	73	0.015	WINNER: English-only
```

## Local-system guardrails (Apple Silicon)

These bite hard if you ignore them:

- **Single-GPU saturation.** Apple Silicon processes one ASR/LLM job at a time. Running two in parallel halves each (verified 2× slowdown in practice). Stay sequential.
- **Pre-flight kill.** `pgrep -if "superwhisper|whisper|asr|aiserver"`. Any other ASR consumer running = pause it. A background ASR consumer (e.g. SuperWhisper) has been observed to cause a ~14× RTF regression mid-batch.
- **dtype.** fp16 is the Apple Silicon default and tested floor. fp32 has no measured benefit. int8 is sometimes OK; **int4 visibly degrades ASR** and is suspect for any quality-sensitive workload. Don't quantize without a baseline.
- **MLX > Core ML > Metal > CPU** for Python workflows. Unified memory zero-copy beats conversion overhead.
- **Model defaults are often wrong.** Two concrete cases:
  - `parakeet-mlx` CLI defaults to `parakeet-tdt-0.6b-v3` (multilingual). For English, v2 is ~4 WER points better. **Always pass `--model`.**
  - HuggingFace "default" Whisper means `whisper-1` which is OpenAI's hosted endpoint, not local. Specify the local repo (`mlx-community/whisper-large-v3-turbo`).
- **Memory accounting.** 1.7B fp16 ≈ 8 GB resident; Whisper turbo ≈ 3 GB; 30B q4 ≈ 18 GB. Plan for headroom; don't run two large models simultaneously.
- **Thermal / sustained-load throttling.** Whisper turbo throughput has been seen to drop from ~6000 → ~2000 frames/s after ~80 min of sustained load. Long batches: budget for ~30% slowdown vs cold benchmark.

## Common rationalizations — STOP if you catch yourself thinking these

| Rationalization | Reality |
|---|---|
| "I can tell which is better by listening / reading the output." | Two configs that look identical to the eye can differ by 4 WER points. Get the number. |
| "Let me try a few combinations at once." | You'll have no idea which knob mattered. Revert and serialize. |
| "The fast model is obviously the right choice." | The faster model can also be the more accurate one — but error *profiles* differ (one family may nail a proper noun another misspells). Tradeoffs are real; measure both. |
| "I'll skip the baseline — defaults are good." | A CLI's default model is sometimes the *wrong* one for your language/task. |
| "Cold-run RTF is what I'll quote." | It includes the model-hub download. The number you commit to is the warm-cache run. |
| "It worked last time, no need to re-bench." | Library upgrades, OS updates, and background indexing all silently move the floor. Re-bench. |
| "Parallel will be faster." | Apple Silicon GPU saturates — 2 jobs halve each. Verified repeatedly. |
| "More context priming is always better." | A long initial_prompt can buy +1 NE recall but introduce a hallucinated title at the top of the transcript. Marginal wins can come with non-marginal artifacts. |
| "I'll log results after I finish iterating." | You'll forget the configs by run 4. Append immediately. |

## Red flags — STOP and restart from baseline

- Comparing runs without a fixed eval set
- Two configs changed in one run
- "I'll measure later" / no `results.tsv` yet
- Adopting a winner without checking it on a second held-out input
- Quoting cold-run RTF as steady-state
- Calling something "the best" without a number next to it

## Worked example — picking a local ASR model (illustrative)

Goal: pick the best local ASR model for English audio on a single Apple Silicon laptop.

**Eval:** one frozen ~30-min English audio clip + a hand-checked reference transcript (`gold.txt`). Primary metric: WER via `jiwer`. Secondary: RTF, named-entity recall on a frozen domain glossary.

**Runs** (`_experiments/<topic>/results.tsv`):

| # | Knob changed | WER | RTF | Verdict |
|---|---|---:|---:|---|
| 01 | model defaults (cold) | 12.3% | 0.019 | baseline — the CLI default was a multilingual variant |
| 02 | switch to the English-only variant | **8.0%** | **0.015** | WINNER — more accurate AND faster |
| 03 | swap to a different ASR family, no prompt | 8.1% | 0.022 | tied on WER, slower, but different error profile on proper nouns |
| 04 | run 03 + domain `initial_prompt` | 8.1% | 0.027 | +1 NE recall but introduced a hallucinated header — net marginal |

*(Numbers are illustrative but representative of a real tuning session.)*

**Findings, ranked by surprise:**
1. The CLI default model was the wrong one — several WER points gained just by selecting the task-appropriate variant.
2. A domain `initial_prompt` is double-edged: small recall gains can arrive with hallucinated artifacts.
3. Two model families reached comparable WER with *different error profiles* — one drops proper nouns, the other inserts hallucinated headers under priming. Measure both.

**Total compute: a few minutes of wall time for 4 runs (including all model downloads).** Cheap insurance against shipping the wrong config to a long batch.

This is the standing template — copy the structure when starting a new comparison.

## Where lessons go

When you finish a research session, append a dated entry to the *operational* doc that actually uses the winning config (the runbook/README for that pipeline). This skill teaches the *method*; the operational docs accumulate the *evidence*.

Update this skill only when:
- A new rationalization makes it past the table (add it)
- A new Apple-Silicon-specific guardrail is discovered (add it to the local-system guardrails section)
- The methodology itself changes (rare)
