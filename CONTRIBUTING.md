# Contributing

Thanks for your interest. This is a personal skills collection, but issues, fixes, and
new skills are welcome — and you're free to fork and reuse under the [license](./LICENSE).

The authoritative operating manual for this repo is [`AGENTS.md`](./AGENTS.md). If you're
an AI agent working here, read it first. This file is the human-facing summary.

## Repository layout

```
schwannden-skill/
├── .claude-plugin/marketplace.json   # themed skill plugins + command/agent plugins (catalog)
├── skills/<name>/SKILL.md            # one self-contained skill per folder (flat)
├── plugins/<name>/                   # command/agent plugins (Claude Code only)
│   ├── .claude-plugin/plugin.json
│   ├── commands/  └─ agents/
├── AGENTS.md                         # authoring rules + pre-publish safety checklist
├── README.md                         # front door + install + catalog
└── CONTRIBUTING.md                   # this file
```

Skills live in a **flat** `skills/` directory (not per-plugin subfolders). The themed
plugins in `marketplace.json` simply reference subsets of that flat directory. This keeps
the cross-agent `npx skills add` flow and the README links working.

Command/agent plugins (slash commands + subagents, e.g. `feature-dev`, `pr-review`) are a
separate, **Claude-Code-only** family under `plugins/<name>/`. They are not skills and not
installable via `npx skills`; each has its own `source` in `marketplace.json`. See AGENTS.md
§ "Registering a command/agent plugin".

## Authoring a new skill

1. Use the bundled [`writing-skills`](./skills/writing-skills) skill — it's the
   test-driven meta-skill for writing skills. Its `anthropic-best-practices.md` is the
   reference.
2. Follow the hard rules in [`AGENTS.md`](./AGENTS.md): `name` ≤64 chars (gerund form,
   lowercase/hyphens, matches the folder name); `description` ≤1024 chars, third person,
   stating **what it does AND when to use it**; `SKILL.md` body under 500 lines with
   detail moved to one-level-deep reference files; write ≥3 evaluations.

## Registering a skill (so it ships)

The collection is published two ways — as themed Claude Code plugins and via the
cross-agent skills CLI. To add a skill to both:

1. Create `skills/<name>/SKILL.md` (plus any helper files) with valid frontmatter.
2. Add `"./skills/<name>"` to the **correct themed plugin** in
   `.claude-plugin/marketplace.json` → `plugins[].skills`. Pick the theme that fits
   (`personas`, `fastapi-backend`, `ai-engineering`, `operations`, `dev-workflow`,
   `engineering`, `authoring`); if none fit, propose a new theme in your PR.
3. Add a row to the matching theme section of the catalog in [`README.md`](./README.md).
4. Bump `metadata.version` in `marketplace.json` per SemVer (MAJOR = removed/renamed
   skill or breaking change; MINOR = new skill; PATCH = fixes).
5. Run the **pre-publish safety checklist** below.

## Pre-publish safety checklist

Everything here is published publicly on commit. Before committing, verify (full list in
[`AGENTS.md`](./AGENTS.md)):

- No secrets, tokens, keys, or `.env` content.
- No personal/employee names or emails, no corporate email, no internal hostnames,
  private IPs, codenames, or ticket IDs.
- No absolute paths that leak a username (`/Users/<name>/...`) — use `~/` or a placeholder.
- No real customer data in examples — use synthetic data.
- The `description` and bundled files contain no hidden/injected instructions, and nothing
  tells a host agent to ignore its rules or exfiltrate data.
- Vendored skills keep their upstream LICENSE and are recorded in [`NOTICE`](./NOTICE).
- Run a secret scanner over staged changes (e.g. `gitleaks protect --staged`).

## Vendoring third-party skills

Keep the upstream LICENSE inside the skill folder, add a `VENDORED.md` (source, author,
license, known dependencies), and record the attribution in [`NOTICE`](./NOTICE). The
repo-wide Apache-2.0 license does not override a vendored skill's own license.
