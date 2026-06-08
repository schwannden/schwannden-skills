# schwannden-skill

A personal, public collection of **agent skills** — reusable `SKILL.md` instruction
sets that extend AI coding agents. The skills are plain Markdown and portable across
[30+ agents](https://agentskills.io) (Claude Code, Cursor, Codex, GitHub Copilot,
Windsurf, Cline, and more); they're also packaged as themed Claude Code plugins for
one-command install.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Agent Skills spec](https://img.shields.io/badge/spec-agentskills.io-7c3aed.svg)](https://agentskills.io)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](./CONTRIBUTING.md)

## Contents

- [What are skills?](#what-are-skills)
- [Quickstart](#quickstart)
- [Install](#install)
  - [Claude Code (plugins)](#claude-code-plugins)
  - [Any agent (skills CLI)](#any-agent-skills-cli)
  - [Manual](#manual)
- [Compatibility](#compatibility)
- [Skill catalog](#skill-catalog)
- [Plugins (commands + agents)](#plugins-commands--agents)
- [Contributing](#contributing)
- [License](#license)

## What are skills?

A skill is a folder with a `SKILL.md` file — YAML frontmatter (`name` + `description`)
plus instructions and optional helper files. Agents load a skill on demand when its
description matches what you're doing. See the [Agent Skills spec](https://agentskills.io)
and [Anthropic's docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview).

## Quickstart

Install everything into your agent with the [`skills`](https://github.com/vercel-labs/skills) CLI:

```bash
npx skills add schwannden/schwannden-skills --all
```

Prefer one skill? `npx skills add schwannden/schwannden-skills --skill writing-skills`

## Install

Pick the path that matches your tool. Everything below installs from this repo's
flat `skills/` directory, so no matter how you install, you get the same skills.

### Claude Code (plugins)

The skills are grouped into **themed plugins** so you can install just what you want.
First register the marketplace, then install one or more themes:

```text
/plugin marketplace add schwannden/schwannden-skills
/plugin install personas@schwannden-skills
/plugin install fastapi-backend@schwannden-skills
```

Available skill plugins: `personas`, `fastapi-backend`, `ai-engineering`, `operations`,
`dev-workflow`, `authoring`, `engineering` (see the [catalog](#skill-catalog) for what's in
each). Two additional **command/agent plugins** — `feature-dev` and `pr-review` — bundle slash
commands and subagents; see [Plugins (commands + agents)](#plugins-commands--agents).

Plugin skills are namespaced by plugin name when invoked directly, e.g.
`/personas:persona-leadership`.

### Any agent (skills CLI)

The [`skills`](https://github.com/vercel-labs/skills) CLI installs into 18+ agents and
works with plain git URLs — no marketplace needed:

```bash
# Everything, into the agent the CLI detects in the current project
npx skills add schwannden/schwannden-skills --all

# A single skill
npx skills add schwannden/schwannden-skills --skill transcribing-media

# Target specific agents, installed globally (~/<agent>/skills)
npx skills add schwannden/schwannden-skills -a cursor -a codex -a github-copilot -g

# See what's available without installing
npx skills add schwannden/schwannden-skills --list
```

Supported `-a` values include `claude-code`, `cursor`, `codex`, `github-copilot`,
`windsurf`, `cline`, `continue`, `opencode`, and many more.

### Manual

Every skill is a self-contained folder under [`skills/`](./skills). Copy the one you
want into your agent's skills directory:

```bash
# Claude Code — global (all projects)
cp -R skills/writing-skills ~/.claude/skills/

# Claude Code — single project
cp -R skills/writing-skills .claude/skills/
```

Other agents use their own location (e.g. `.cursor/skills/`, `.codex/skills/`); check
your agent's docs.

## Compatibility

The skills themselves are just `SKILL.md` files following the open
[Agent Skills spec](https://agentskills.io), so they work in any agent that supports
the standard. The `.claude-plugin/marketplace.json` in this repo is an *additional*
convenience layer that enables Claude Code's native `/plugin install` — it doesn't
lock the skills to Claude. A few skills reference optional MCP servers (e.g. `context7`)
or external CLIs in their bodies; those are noted in the skill and degrade gracefully.

## Skill catalog

20 skills across 7 themes. Each theme maps to a Claude Code plugin (install line shown);
with the skills CLI, install any single skill with `--skill <name>`.

### 🎭 personas — `/plugin install personas@schwannden-skills`

| Skill | Description | Notes |
|-------|-------------|-------|
| [`persona-technical-writing`](./skills/persona-technical-writing) | Technical-writing persona — opinionated, evidence-driven blog posts and engineering essays | Original |
| [`persona-spiritual`](./skills/persona-spiritual) | Reflective/spiritual writing persona for personal essays on faith and the ordinary (Peterson/Buechner tradition) | Original |
| [`persona-leadership`](./skills/persona-leadership) | Leadership-coaching thought partner for reviews, feedback, 1:1 prep, and team planning — coaches, doesn't write | Original |

### 🐍 fastapi-backend — `/plugin install fastapi-backend@schwannden-skills`

| Skill | Description | Notes |
|-------|-------------|-------|
| [`writing-fastapi-apis`](./skills/writing-fastapi-apis) | Building FastAPI endpoints — a uniform success/error envelope, hierarchical error codes, one central exception handler, i18n via `message_key`, PII-redaction discipline, and SSE error events | Original |
| [`testing-async-fastapi`](./skills/testing-async-fastapi) | Testing an async FastAPI + Postgres + LLM app — pytest-asyncio, httpx `ASGITransport`, a throwaway transactional-rollback test database, and faking the LLM client at the SDK boundary | Original |
| [`dockerizing-fastapi-uv`](./skills/dockerizing-fastapi-uv) | Containerizing a Python 3.12 + FastAPI + uv service — multi-stage Dockerfiles, BuildKit cache mounts, non-root images, hot-reload compose, and GitHub Actions deploy to Cloud Run via Workload Identity Federation | Original |
| [`writing-drf-apis`](./skills/writing-drf-apis) | Django REST Framework best practices for consistent views, serializers, and coded error responses — with a unified exception-handler pattern | Original |

### 🤖 ai-engineering — `/plugin install ai-engineering@schwannden-skills`

| Skill | Description | Notes |
|-------|-------------|-------|
| [`building-llm-agent-loops`](./skills/building-llm-agent-loops) | Building a thin agent loop on the Anthropic Python SDK — a stable `tools` array for prompt caching, `allowed_domains` security, `cache_control` placement, `pause_turn` re-entry, and the `stop_reason` dispatch matrix | Original |
| [`comparing-model-variants`](./skills/comparing-model-variants) | Comparing local ML model variants and tuning inference configs — disciplined one-knob-at-a-time empirical comparison on local hardware | Original |
| [`transcribing-media`](./skills/transcribing-media) | Transcribing audio, video, or YouTube to text with the best LOCAL pipeline for your machine — multilingual Whisper by default, with opt-in English and Mandarin/Chinese specialists | Original |

### 📟 operations — `/plugin install operations@schwannden-skills`

| Skill | Description | Notes |
|-------|-------------|-------|
| [`monitoring-services`](./skills/monitoring-services) | Tool-agnostic service monitoring with self-maintained baselines, causal closure, and known-chronic suppression — refreshes its own thresholds as the system evolves; a template for any metrics backend | Original |
| [`triaging-incidents`](./skills/triaging-incidents) | Tool-agnostic incident triage that classifies a report, routes to a symptom playbook, diagnoses to root cause, and captures what it learned back into the skill so triage compounds | Original |

### 🔧 dev-workflow — `/plugin install dev-workflow@schwannden-skills`

| Skill | Description | Notes |
|-------|-------------|-------|
| [`explain-pr`](./skills/explain-pr) | Warm up a groggy reviewer before a PR review — paced walkthrough of what changed and why, with ASCII flow diagrams; orients, does not critique | Original |
| [`dependency-upgrade-scanner`](./skills/dependency-upgrade-scanner) | Read-only batch scan of open dependency-upgrade PRs into one prioritized migration-risk report; dispatches parallel per-library analysis subagents | Original |
| [`recipe-atlassian`](./skills/recipe-atlassian) | Direct `curl` recipes for Jira Cloud and Confluence Cloud REST APIs — search, issue/page CRUD, transitions, attachments, ADF and storage-format references | Original |

### 🛠️ engineering — `/plugin install engineering@schwannden-skills`

Process across the build lifecycle — design, build, review. The `developing-features`
and `reviewing-code` skills are portable, cross-agent counterparts of the `feature-dev`
and `pr-review` command plugins (they don't reproduce the plugins' interactive
confirmation gates exactly, since those rely on Claude-Code-only tooling).

| Skill | Description | Notes |
|-------|-------------|-------|
| [`system-design`](./skills/system-design) | Vendor-neutral design partner for distributed systems — four modes (Review, Rubber-duck, Autopilot, Interview), a nine-dimension rubric with an L5/L6 interview scorecard, and a 15-design reference library spanning the canonical archetypes; reasons in fundamentals over branded products | Original |
| [`developing-features`](./skills/developing-features) | Building a non-trivial feature end-to-end — a multi-phase loop (explore → clarify → architect → implement → review) with parallel read-only subagents and structured decision gates; skips itself for typo/one-line/hotfix changes | Original |
| [`reviewing-code`](./skills/reviewing-code) | Reviewing a diff across six lenses (logic bugs, silent failures, test coverage, type design, comment accuracy, simplification) with confidence filtering and adversarial verification so only high-signal findings surface | Original |

### ✍️ authoring — `/plugin install authoring@schwannden-skills`

| Skill | Description | Notes |
|-------|-------------|-------|
| [`writing-skills`](./skills/writing-skills) | Creating, editing, or verifying skills before deployment — test-driven process documentation | Vendored from [obra/superpowers](https://github.com/obra/superpowers), MIT |
| [`agents-md`](./skills/agents-md) | Creating, improving, or reviewing an `AGENTS.md` file — templates, section guidance, and anti-patterns for the open agent-instructions standard | Original |

## Plugins (commands + agents)

Beyond skills, the repo ships two **Claude-Code-only** plugins that bundle a slash command
with its specialist subagents. Unlike skills, these are *not* portable via the `npx skills`
CLI — install them through the marketplace:

```text
/plugin marketplace add schwannden/schwannden-skills
/plugin install feature-dev@schwannden-skills
/plugin install pr-review@schwannden-skills
```

| Plugin | Provides | What it does |
|--------|----------|--------------|
| [`feature-dev`](./plugins/feature-dev) | `/feature-dev` command + `code-explorer`, `code-architect` agents | Gated feature workflow: explore the codebase → clarify → design 2–3 architectures → implement → auto-review. Three user-confirmation checkpoints before any code is written. |
| [`pr-review`](./plugins/pr-review) | `/review-pr` command + `code-reviewer`, `pr-test-analyzer`, `doc-analyzer`, `silent-failure-hunter`, `type-design-analyzer`, `code-simplifier` agents | Inspects the diff, dispatches the applicable specialist agents (in parallel on request), and aggregates findings into Critical / Important / Suggestions / Strengths. |

`feature-dev`'s final phase hands off to `pr-review` when both are installed, and degrades to
an inline review otherwise. Both are language/framework-agnostic and load any installed domain
skill whose description matches what they're working on.

## Contributing

This is a personal collection, but contributions and reuse are welcome. The authoring
workflow, registration steps, and the **pre-publish safety checklist** are in
[`CONTRIBUTING.md`](./CONTRIBUTING.md) and [`AGENTS.md`](./AGENTS.md) — any agent working
in this repo should read `AGENTS.md` first. New skills are authored using the bundled
[`writing-skills`](./skills/writing-skills) skill.

## License

Repository content is licensed under [Apache-2.0](./LICENSE), except vendored
third-party skills, which retain their own licenses (recorded in [`NOTICE`](./NOTICE)
and in each skill folder).

> Disclaimer: these skills are provided as-is. Review any skill before relying on it —
> installing a skill can grant an agent the ability to run its bundled scripts.
