# AGENTS.md

Operating manual for any AI agent working in this repository. This is a
**public** collection of installable agent skills. Two rules dominate everything
else here:

1. **Author skills well** — follow the authoring rules in this file.
2. **Never leak private data** — every skill is published publicly; run the
   pre-publish safety checklist before any commit.

> This file is the source of truth. `CLAUDE.md`, if present, should just point
> here so Claude Code and AGENTS.md-aware agents read the same instructions.

---

## What this repo is

`schwannden-skill` is a personal, public collection of [agent skills](https://agentskills.io)
— Markdown `SKILL.md` files (plus optional helper files) that extend AI coding
agents (Claude Code, Cursor, Codex, etc.).

Anyone can install skills from here:

```bash
# vercel-labs/skills CLI (cross-agent)
npx skills add schwannden/schwannden-skills

# or as a Claude Code plugin marketplace
/plugin marketplace add schwannden/schwannden-skills
```

Because installation is by git URL, **whatever is committed here is public the
moment it is pushed.** Treat the repo as publish-on-commit.

---

## Repository layout

```
schwannden-skill/
├── .claude-plugin/marketplace.json   # registers skills + plugins for Claude Code install
├── skills/
│   └── <skill-name>/
│       ├── SKILL.md                  # REQUIRED: frontmatter + instructions
│       ├── references/               # optional, loaded on demand
│       ├── scripts/                  # optional executable helpers
│       └── LICENSE + VENDORED.md     # ONLY for vendored (third-party) skills
├── plugins/                          # command/agent plugins (Claude Code only, NOT skills)
│   └── <plugin-name>/
│       ├── .claude-plugin/plugin.json  # plugin manifest (name, description, version)
│       ├── commands/<cmd>.md          # slash commands (auto-discovered)
│       └── agents/<agent>.md          # subagents (auto-discovered)
├── AGENTS.md                         # this file
├── README.md                         # human front door + catalog
├── LICENSE                           # Apache-2.0 (repo-wide default)
└── NOTICE                            # third-party attributions (Apache requirement)
```

**Two artifact families live here:**

1. **Skills** (the bulk of the repo) — portable `SKILL.md` files in a **flat**
   `skills/` directory, installable cross-agent via `npx skills add` AND as
   Claude Code plugins.
2. **Command/agent plugins** — Claude-Code-only bundles of slash commands +
   subagents under `plugins/<name>/`. These are NOT skills, are NOT installable
   via the cross-agent `npx skills` CLI, and each gets its **own** `source` in
   `marketplace.json` (e.g. `"./plugins/feature-dev"`) so their `commands/` and
   `agents/` auto-discover in isolation instead of leaking into the `source: "./"`
   skill plugins.

**Conventions**
- One skill per folder under `skills/`. The folder name MUST equal the `name`
  in that skill's frontmatter.
- Skill names: lowercase `a-z0-9-`, ≤64 chars, no leading/trailing/consecutive
  hyphens. Prefer **gerund form** (`writing-skills`, `processing-pdfs`).
- Reference files live **one level deep** from `SKILL.md` (agents only partially
  read deeply nested chains).
- The "flat `skills/`, no per-plugin subfolders" rule below applies to **skills
  only** — it exists to keep the `npx skills` flow working. Command/agent plugins
  are not skills and DO live in their own `plugins/<name>/` subfolders.
- Plugin command/agent files obey the same **pre-publish safety checklist** as
  skills (no internal names, paths, emails, ticket IDs, secrets). Agents must
  never invoke other agents — the command orchestrates; an agent may only
  *suggest* a follow-up agent.

---

## How to author a new skill

**Use the `writing-skills` skill in this repo** — it is the meta-skill for
authoring skills (TDD-for-process: watch an agent fail without the skill before
you write it). Its `anthropic-best-practices.md` is the authoritative reference.

Hard rules, enforced on every skill (from Anthropic's skill-authoring best
practices):

- **`name`** (frontmatter, required): ≤64 chars, lowercase/numbers/hyphens, no
  XML tags, must NOT contain the words `anthropic` or `claude`. Gerund form.
- **`description`** (frontmatter, required): ≤1024 chars, **third person**,
  states **both what the skill does AND when to use it** (the trigger). This
  string is injected into the installer's system prompt — it is how the agent
  decides to load the skill. Never "I can help you…" / "You can use this to…".
- **Body** of `SKILL.md`: keep under **500 lines**. Move detail into reference
  files and link to them (progressive disclosure).
- Reference files over 100 lines start with a table of contents.
- Forward-slash paths only. List required packages. Fully-qualify MCP tool
  names (`ServerName:tool_name`).
- Scripts handle their own errors; no magic constants; state "run this" vs
  "read this as reference" explicitly.
- Write **≥3 evaluations** (pressure scenarios) before writing extensive docs,
  and test with the models you actually target.

To scaffold a starting `SKILL.md`: `npx skills init <skill-name>`.

---

## Pre-publish safety checklist (RUN BEFORE EVERY COMMIT)

A published skill's text — including its `description` — runs inside other
people's agents. Scrubbing is a **security** requirement, not tidiness.
Automated scanners catch patterned secrets but **miss free-form PII** (names,
usernames in paths, internal codenames) — so a manual read pass is mandatory.

Verify, for every changed file (including scripts, configs, sample data, images):

- [ ] No API keys, tokens, OAuth secrets, private keys, `.env` files, cloud creds.
- [ ] No personal/employee names, emails, or phone numbers. **In particular, no
      `@ui.com` corporate email** — this is a personal repo; use
      `schwannden@gmail.com` only where an email is genuinely needed.
- [ ] No absolute paths that leak a username — replace `/Users/schwanndenkuo/...`
      and `/home/<name>/...` with `~/` or a `<placeholder>`.
- [ ] No internal hostnames, private IPs, intranet/VPN URLs, DB connection
      strings, or company-internal product names / codenames / ticket IDs /
      Slack / Jira / internal repo links.
- [ ] No real customer or account data in examples — use synthetic data.
- [ ] The `description` contains no hidden or injected instructions.
- [ ] No instruction tells the host agent to ignore its own rules, to follow
      directives found in fetched/tool content, or to send file contents to a
      network endpoint (prompt-injection / data-exfiltration review).
- [ ] If the skill is vendored from a third party, its upstream LICENSE is
      preserved in the skill folder and recorded in `NOTICE` (see below).
- [ ] Ran a secret scanner over staged changes (see below).

### Automated enforcement (pre-commit hooks)

This checklist is wired into [`pre-commit`](https://pre-commit.com) so it runs on
every commit instead of relying on memory. One-time setup:

```bash
uv tool install pre-commit   # or: pipx install pre-commit / brew install pre-commit
pre-commit install           # installs the pre-commit + commit-msg hooks
```

`.pre-commit-config.yaml` runs, on each commit: file hygiene (whitespace, EOF,
JSON/YAML parse), `markdownlint-cli2`, **gitleaks** (secret scanning), a
**PII guard** (`scripts/check-no-pii.sh` — corporate email, home paths,
username), the **registration + frontmatter** check (`scripts/check-registration.py`),
and **gitlint** (Conventional Commits on the message). The manual read pass above
is still required — scanners miss free-form PII.

Run everything on demand, or scan history before the first push:

```bash
pre-commit run --all-files       # run all hooks over the whole repo
gitleaks detect --verbose        # scan full git history for secrets
```

Also enable **GitHub secret scanning + push protection** as a server-side
backstop (local hooks can be bypassed with `--no-verify`).

---

## Registering a new skill (do this for every skill you add)

Skills live in a **flat** `skills/` directory. `.claude-plugin/marketplace.json`
exposes them as **themed plugins** — each plugin entry uses `source: "./"` and an
inline `skills` array selecting a subset of the flat directory. Do NOT move skills
into per-plugin subfolders (it would break the cross-agent `npx skills add` flow
and the README links).

1. Create `skills/<name>/SKILL.md` with valid `name` + `description`.
2. Add `"./skills/<name>"` to the **correct themed plugin** in
   `.claude-plugin/marketplace.json` → the matching `plugins[].skills` array.
   Current themes: `personas`, `fastapi-backend`, `ai-engineering`, `operations`,
   `dev-workflow`, `engineering`, `authoring`. If none fit, add a new plugin entry (same shape:
   `name`, `description`, `source: "./"`, `strict: false`, `category`, `tags`,
   `skills`).
3. Add a row to the matching **theme section** of the catalog in `README.md`.
4. Bump `metadata.version` in `marketplace.json` per SemVer (MINOR for a new skill).
5. Run the pre-publish safety checklist above.
6. Run `python3 scripts/check-registration.py` — it must print `✓` before you commit.

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the human-facing version of this.

---

## Renaming or removing a skill (the step everyone forgets)

Creating a skill is only one third of the lifecycle. **Renaming or deleting one
touches the SAME linkage files** — and skipping them leaves dangling references
that ship publicly. Both operations are governed by one rule:

> **The registration invariant:** the set of `skills/<name>/` folders, the
> `./skills/<name>` entries across all themed plugins in `marketplace.json`, and
> the catalog rows in `README.md` must be **identical**. Same for
> `plugins/<name>/` ↔ each plugin's isolated `source`. Every create/rename/delete
> must restore this invariant in the **same commit**.

**To rename or move a skill** (e.g. `drf-expert` → `writing-drf-apis`), update
all of these together:
1. Rename the folder `skills/<old>/` → `skills/<new>/`.
2. Update the frontmatter `name:` inside `SKILL.md` to match the new folder.
3. Update its `./skills/<old>` entry in the themed plugin's `skills` array.
4. Update its catalog row in `README.md`.
5. Grep for cross-references and fix them: `grep -rn "<old>" . --exclude-dir=.git`
   (other skills, READMEs, this file — anywhere the old name is mentioned/linked).
6. Bump `metadata.version` — a rename is a **MAJOR** bump (install URLs change).

**To remove a skill**, do the inverse:
1. Delete the `skills/<name>/` folder.
2. Remove its `./skills/<name>` entry from the themed plugin's `skills` array
   (and delete the whole plugin entry if it was the last skill in that theme).
3. Remove its catalog row from `README.md`.
4. Grep for and remove dangling cross-references (step 5 above).
5. Bump `metadata.version` — a removal is a **MAJOR** bump.

The same procedure applies to command/agent plugins, substituting
`plugins/<name>/` and its isolated `source` entry for the skill folder/`skills`
array.

**Verify before every commit** — the one command that catches all of the above:

```bash
python3 scripts/check-registration.py
```

It asserts the invariant (disk ↔ `marketplace.json` ↔ `README.md`, frontmatter
`name` == folder, valid JSON) and exits non-zero with a report on any drift.

---

## Registering a command/agent plugin

Command/agent plugins (e.g. `feature-dev`, `pr-review`) are Claude-Code-only and
live under `plugins/<name>/`, not in the flat `skills/` directory.

1. Create the plugin tree:
   - `plugins/<name>/.claude-plugin/plugin.json` — manifest with `name`,
     `description`, `version`, `author`. (`name` must equal the folder name and
     must NOT contain `claude`/`anthropic`.)
   - `plugins/<name>/commands/<command>.md` — slash command(s). Frontmatter:
     `description`, `argument-hint` (optional), `allowed-tools`.
   - `plugins/<name>/agents/<agent>.md` — subagent(s). Frontmatter: `name`,
     `description` (third person, states what + when), `tools`, `model`.
   `commands/` and `agents/` MUST sit at the plugin root, never inside
   `.claude-plugin/`.
2. Add a `plugins[]` entry to `marketplace.json` with its **own** isolated
   `source: "./plugins/<name>"` (NO `skills` array — commands/agents are
   auto-discovered by convention). Include `category` and `tags`.
3. Add the plugin to the **Plugins (commands + agents)** section of `README.md`.
4. Bump `metadata.version` per SemVer (MINOR for a new plugin).
5. Run the pre-publish safety checklist. Keep these portable: reference domain
   skills only as optional ("load any installed skill whose description matches"),
   never hard-code a private skill list, and don't reference an agent/command that
   isn't shipped here.
6. Run `python3 scripts/check-registration.py` — it must print `✓` before you commit.

---

## Vendored (third-party) skills

When copying a skill from another repo (e.g. `writing-skills` from
`obra/superpowers`):

- Keep the upstream LICENSE file inside the skill folder.
- Add a `VENDORED.md` recording source URL, author, license, and any known
  cross-skill dependencies.
- Record the attribution in the top-level `NOTICE`.
- The repo-wide Apache-2.0 license does **not** override a vendored skill's
  own license.

---

## Versioning & commits

- Version the collection as a whole with SemVer in `marketplace.json`
  (`metadata.version`) + git tags (`vX.Y.Z`). MAJOR = removed/renamed skill or
  breaking frontmatter change; MINOR = new skill/capability; PATCH = fixes.
- Commit with the personal identity (`schwannden@gmail.com`), never the
  corporate one.
- Push only when the user explicitly asks.
