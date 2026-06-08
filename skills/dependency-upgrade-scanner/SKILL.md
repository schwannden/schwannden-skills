---
name: dependency-upgrade-scanner
description: |-
  Scan all open dependency upgrade pull requests and produce a consolidated migration risk report. Use when: (1) User wants to review all pending dependabot/dependency PRs at once, (2) User asks "what dependency PRs are safe to merge?", (3) User wants a batch assessment of library upgrades, (4) User asks to scan dependencies. This skill is READ-ONLY — it never merges PRs or modifies code. It dispatches parallel subagents (one per PR) and aggregates results into a single prioritized report. Examples are Python/pyproject.toml-centric but the workflow generalizes to any ecosystem (npm, Cargo, Go modules) — swap the manifest file accordingly.
---

# Dependency Upgrade Scanner

Scan all open dependency upgrade PRs, analyze each in parallel, and produce a consolidated risk report. This is a **read-only** operation — no PRs are merged, no code is changed.

## Workflow

### Step 1: Discover Dependency PRs

Fetch all open PRs with the `dependencies` label:

```bash
gh pr list --state open --label dependencies --json number,title,headRefName,labels
```

Parse each PR title to extract: **library name**, **current version**, **target version**.

Dependabot PR titles follow patterns like: `bump <library> from <current> to <target>` or `deps(deps): bump <library> from <current> to <target>`.

Also check for PRs matching a `dependabot/` branch prefix that may lack labels.

### Step 2: Read the Dependency Manifest

Read the project's dependency manifest (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, etc.) to determine:
- Whether each library is a **production** or **dev-only** dependency
- The exact pinned version (to confirm the PR's "from" version)
- Whether the library exists at all (catch stale PRs for removed deps)

For Python with `pyproject.toml`, dev dependencies are typically under `[dependency-groups] dev` or `[project.optional-dependencies]`.

### Step 3: Dispatch Parallel Subagents

For each dependency PR, launch a subagent via the `Agent` tool (use the `general-purpose` agent type, or a dedicated analysis agent if your setup has one). Launch **all agents in a single message** to maximize parallelism.

Give each agent the analysis workflow from `references/library-migration-analysis.md` plus this context:

```
Analyze the following library upgrade for this codebase. Follow the analysis
workflow in references/library-migration-analysis.md exactly (gather intelligence,
audit usage, assess risk, produce report). Produce a read-only report only — do
NOT change code or merge anything.

- Library: <name>
- Current version: <current>
- Target version: <target>
- PR number: <number>
- Dependency group: production | dev-only
- Project root: <project_root>
```

### Step 4: Collect and Aggregate Reports

After all agents complete, organize their reports into a single consolidated output.

**Group by risk level** (highest first):

1. **Critical** — Needs migration plan, do not merge
2. **High Risk** — Code changes required before merge
3. **Medium Risk** — Careful review needed
4. **Low Risk** — Likely safe, verify with tests
5. **Safe** — Merge as-is

**Within each risk group**, sort by:
- Production dependencies before dev-only
- Major bumps before minor before patch

### Step 5: Produce Final Report

Output the consolidated report in this format:

```markdown
# Dependency Upgrade Scan Report

**Date:** <today>
**Open dependency PRs:** <count>
**Scanned:** <count>

## Summary

| Risk | Count | Libraries |
|------|-------|-----------|
| Critical | N | lib1, lib2 |
| High Risk | N | lib3 |
| Medium Risk | N | lib4, lib5 |
| Low Risk | N | lib6 |
| Safe | N | lib7, lib8, lib9 |

## Safe to Merge (no action needed)

<List each Safe library with PR number, one line each>

## Low Risk (run tests to confirm)

<List each Low Risk library with brief rationale>

## Medium Risk (review recommended)

<Full report for each library>

## High Risk (code changes required)

<Full report for each library, with specific action items>

## Critical (migration plan required)

<Full report for each library>

## Potentially Unused Libraries

<Any libraries flagged as unused by the agents>

## Recommended Merge Order

<Numbered list suggesting which PRs to merge first, based on risk and dependency relationships>
```

## Important Constraints

- **Never merge PRs.** This skill is read-only.
- **Never modify code.** Analysis only.
- **Be transparent about gaps.** If an agent could not find a changelog, say so in the report.
- **Respect rate limits.** If there are >15 dependency PRs, consider batching agents in groups of 8-10 to avoid overwhelming the system.
- **Flag version conflicts.** If two PRs upgrade libraries that depend on each other, note the potential conflict.

## Reference Files

- **`references/library-migration-analysis.md`** — The per-library analysis workflow each subagent should follow. Read/pass this when dispatching agents in Step 3.
