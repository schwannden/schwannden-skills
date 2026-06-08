---
name: agents-md
description: Expert guidance for writing high-quality AGENTS.md files. Use when the user wants to create, improve, or review an AGENTS.md file for a project or repository. AGENTS.md is the open standard for giving AI coding agents project-specific instructions — a README for agents. Trigger when user mentions writing an AGENTS.md, creating agent instructions, configuring AI coding tools, or asks "what should I put in AGENTS.md".
---

# AGENTS.md Expert

AGENTS.md is an open Markdown standard (supported by 25+ AI coding tools including Claude Code, GitHub Copilot, Cursor, Codex, Devin, Factory) that gives AI coding agents a dedicated briefing file. A well-written AGENTS.md reduces agent discovery time, cuts token usage, and improves task completion.

## Core Principles

**Keep it small and precise.** The file loads on every request. Aim for under 150 lines. Prefer copy-pasteable commands over prose explanations. One real code snippet beats three paragraphs.

**Only include universally relevant content.** Before adding anything, ask: "Is this needed for every task?" If not, move it to a linked reference file or a nested AGENTS.md.

**Treat it like living code.** Outdated instructions actively harm agents. Update it when commands or processes change.

**Progressive disclosure.** Reference separate docs for domain-specific rules rather than cramming everything into the root file.

## Workflow: Creating an AGENTS.md

### Step 1: Gather Context

Ask the user for (or infer from codebase exploration):
- Primary tech stack with versions (e.g., "Django 4.2, Python 3.12, PostgreSQL 15")
- Package manager (especially if non-standard: uv, pnpm, bun, poetry)
- Test commands and any non-obvious flags
- Non-standard build/lint/typecheck commands
- Monorepo structure (if applicable)
- Key architectural patterns or directories AI should know about
- Things AI repeatedly gets wrong (golden signal for what to document)

### Step 2: Explore the Codebase (if in a repo)

Read these files to extract accurate commands and conventions:
- `package.json` / `pyproject.toml` / `Makefile` — for exact commands
- Existing `README.md` — for setup steps worth repeating concisely
- CI config (`.github/workflows/`) — for test/build commands
- `CLAUDE.md` — for existing agent instructions to consolidate
- `AGENTS.md` — if present, this is an existing AI briefing file; extract commands, conventions, and keep the skill/command reference table

### Step 3: Draft the AGENTS.md

Build the file using the **Six Core Sections** (include only what's relevant):

```markdown
# AGENTS.md

## Project

One sentence. Tech stack with versions. What it does.
Example: "Django 4.2 REST API with PostgreSQL 15 and Redis. Handles accounts, billing, and notifications."

## Setup

Exact commands to get from zero to running. Copy-pasteable.

## Build & Test

Per-file commands first (fast feedback). Full suite commands labeled as "expensive — only when explicitly requested."

## Code Style

- Language/formatter + version (e.g., "Black 24, 120-char line length")
- Key conventions (naming, patterns, anti-patterns to avoid)
- Point to exemplary files, not just rules

## Architecture

Key directories, entry points, important files. What to touch, what to avoid.

## Permissions

✅ Always allowed: reading files, single-file validation, running tests
⚠️ Ask first: installing packages, git operations
🚫 Never: commit secrets, modify production configs, delete files without asking
```

### Step 4: Apply Quality Checks

Before finalizing, verify:
- [ ] Every command is copy-pasteable and works verbatim
- [ ] Stack versions are explicit (not just "React project")
- [ ] No credentials, API keys, or secrets anywhere
- [ ] File is under 150 lines (split into nested files if over)
- [ ] No vague instructions ("run tests properly" → specific command)
- [ ] Per-file commands provided for fast iteration (not just full builds)

### Step 5: Handle Monorepos

For monorepos, use nested AGENTS.md files:
- **Root** `AGENTS.md`: Monorepo overview, workspace navigation, shared tools, global conventions
- **Package-level** `AGENTS.md`: Package purpose, tech stack, package-specific commands
- Nearest file to the edited code takes precedence

Reference separate docs rather than duplicating:
```markdown
For TypeScript conventions, see docs/TYPESCRIPT.md
For testing patterns, see docs/TESTING.md
```

## Reference Files

- **`references/format-guide.md`** — Detailed section templates, good/bad examples, section-by-section guidance. Read when drafting any section in detail.
- **`references/anti-patterns.md`** — Common mistakes and how to fix them. Read when reviewing an existing AGENTS.md or when the user asks what to avoid.
