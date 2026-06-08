# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**[AGENTS.md](./AGENTS.md) is the source of truth.** It covers skill-authoring
rules, the registration workflow, and the pre-publish safety checklist. Read it
before authoring or editing anything. This file is a fast orientation layer; it
does not repeat AGENTS.md.

## What this repo is

A **public, publish-on-commit** collection of agent skills (and a couple of
Claude-Code command/agent plugins). The deliverables are **Markdown files**, not
compiled code — there is **no build system, package manifest, test runner, or
linter**. "Correctness" means: valid frontmatter, internally consistent
registration, and zero leaked private data.

Because installation is by git URL (`npx skills add schwannden/schwannden-skills`
or `/plugin marketplace add schwannden/schwannden-skills`), **anything committed
is public the moment it is pushed.** The pre-publish safety checklist in
AGENTS.md is mandatory before every commit — the biggest risk is a `@ui.com`
corporate email, a leaked `/Users/<name>/...` path, or a secret in an example.

## Two artifact families (the key structural distinction)

This trips up edits — they register **differently** in
`.claude-plugin/marketplace.json`:

1. **Skills** — live in a **flat** `skills/<name>/` directory (one skill per
   folder; folder name MUST equal the frontmatter `name`). They are cross-agent
   installable. In `marketplace.json` they are grouped into **themed plugins**
   that all share `source: "./"` and select skills via an inline `skills` array.
   **Never move skills into per-plugin subfolders** — it breaks the `npx skills`
   flow and README links.
2. **Command/agent plugins** — live under `plugins/<name>/` (Claude-Code-only,
   NOT cross-agent skills). Each gets its **own isolated** `source:
   "./plugins/<name>"` with **no** `skills` array (commands/ and agents/
   auto-discover). `commands/` and `agents/` sit at the plugin root, never
   inside `.claude-plugin/`.

Hard portability rule for plugins: **an agent must never invoke another agent** —
the command orchestrates; an agent may only *suggest* a follow-up. Reference
domain skills only as optional ("load any installed skill whose description
matches"), never hard-code a private skill list.

## Every skill change touches four things in lockstep

Editing just the `SKILL.md` leaves the repo inconsistent. **Creating, renaming,
OR deleting** a skill must keep all four in sync in the same commit:
`skills/<name>/SKILL.md` (folder name == frontmatter `name`) ↔ an entry in the
correct themed plugin's `skills` array in `marketplace.json` ↔ a catalog row in
`README.md` ↔ a SemVer bump of `metadata.version`. A rename or removal is a
**MAJOR** bump and also requires grepping out dangling cross-references to the
old name. Verify with `python3 scripts/check-registration.py` before committing —
it fails on any drift. (See AGENTS.md §§ "Registering a new skill" and "Renaming
or removing a skill" for the full procedures and the plugin equivalent.)

## Frontmatter rules that are enforced

- `name`: ≤64 chars, lowercase/digits/hyphens, gerund form preferred, and **must
  NOT contain the words `claude` or `anthropic`** (the body/description may).
- `description`: ≤1024 chars, **third person**, stating **both what the skill
  does AND when to use it** — this string is injected into the installer's
  prompt and is how an agent decides to load the skill.
- `SKILL.md` body ≤500 lines; reference files live one level deep and start with
  a table of contents when over 100 lines.

## Useful commands (authoring / validation — there is nothing to "build")

```bash
npx skills init <skill-name>          # scaffold a new SKILL.md
python3 scripts/check-registration.py # verify skills/plugins ↔ marketplace.json ↔ README are in sync
gitleaks protect --staged --verbose   # scan staged changes before committing
gitleaks detect --verbose             # scan full history before first push
./skills/writing-skills/render-graphs.js <skill-dir>   # render skill flowcharts to SVG
```

## Vendored skills

A skill copied from a third party (e.g. `writing-skills` from obra/superpowers)
keeps its upstream LICENSE in its folder, records source/author/license in a
`VENDORED.md`, and is attributed in the top-level `NOTICE`. Do not reformat
vendored content to fit this repo's house rules (e.g. the 500-line body cap) —
preserving a clean upstream copy takes priority.

## Commits

Use the personal identity (`schwannden@gmail.com`), never the corporate one.
Push only when explicitly asked.
