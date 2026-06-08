# Library Migration Analysis Workflow

The per-library analysis a subagent runs to assess a single dependency upgrade. The output is a **read-only report** — never change code, merge PRs, or modify files.

Examples below are Python-centric (`pyproject.toml`, PyPI, imports). For other ecosystems, substitute the equivalent: `package.json`/npm, `Cargo.toml`/crates.io, `go.mod`/pkg.go.dev, etc.

## Table of Contents
1. [Input](#input)
2. [Phase 1: Gather Upgrade Intelligence](#phase-1-gather-upgrade-intelligence)
3. [Phase 2: Audit Codebase Usage](#phase-2-audit-codebase-usage)
4. [Phase 3: Risk Assessment](#phase-3-risk-assessment)
5. [Phase 4: Produce Report](#phase-4-produce-report)
6. [Guidelines](#guidelines)

---

## Input

You will receive:
- **Library name** (package registry name)
- **Current version** (what is pinned today)
- **Target version** (what the upgrade proposes)
- **PR number** (optional, for fetching the PR body)
- **Dependency group** (production | dev-only)
- **Project root**

---

## Phase 1: Gather Upgrade Intelligence

**Goal:** Understand every change between current and target version.

1. **Read the PR body** (if PR number provided):
   - Run `gh pr view <number> --json body --jq '.body'`
   - Dependabot PRs often embed release notes and changelogs — extract them.

2. **Find the official changelog / release notes:**
   - Search the web for `<library> changelog`, `<library> release notes`, `<library> CHANGES`, `<library> HISTORY`
   - Check the library's registry page, GitHub releases, and README for links
   - Common locations: `CHANGELOG.md`, `CHANGES.rst`, `HISTORY.md`, `NEWS`, `docs/changelog.rst`

3. **If changelog is insufficient or missing, inspect source code diffs:**
   - Find the library's repository
   - Compare tags: look at the diff between the two version tags
   - Use a web-fetch tool to read the compare URL: `https://github.com/<org>/<repo>/compare/v<current>...v<target>`
   - Focus on: public API changes, removed functions/classes, changed signatures, new required parameters, behavioral changes

4. **Classify the version bump:**
   - **Major** (X.0.0): Expect breaking changes. Scrutinize everything.
   - **Minor** (x.Y.0): New features, possible deprecations. Look for behavioral changes.
   - **Patch** (x.y.Z): Bug fixes only. Still verify — patches occasionally contain surprising changes.

5. **Identify all changes that could affect consumers:**
   - Removed or renamed public APIs (functions, classes, constants, exceptions)
   - Changed function signatures (new required params, removed params, type changes)
   - Changed default values or default behavior
   - Dropped language/runtime version support (check if yours is still supported)
   - Dropped or changed dependency requirements (transitive impact)
   - Security fixes that change behavior (e.g., stricter validation)
   - Deprecation warnings that will become errors in future versions
   - Database/schema changes (for ORM/framework packages)
   - Configuration key renames or removals
   - Changed exception types or error messages

---

## Phase 2: Audit Codebase Usage

**Goal:** Determine exactly how the project uses this library and whether any change impacts it.

1. **Find all direct imports / requires:**
   ```
   Grep for: import <library>, from <library>  (or require/use, per language)
   ```
   Search across all source files in the project. Include test files — test breakage is real breakage.

2. **Find all indirect/configuration usage:**
   - Grep for the library name in settings, config files, `*.cfg`, `*.ini`, `*.yml`, `*.yaml`, `pyproject.toml`
   - For frameworks: check plugin/middleware/app registries (e.g., Django `INSTALLED_APPS`, `MIDDLEWARE`, `REST_FRAMEWORK`)
   - Check for management commands, template tags, or signal handlers from the library

3. **Map specific API usage:**
   - For each breaking/changed API identified in Phase 1, grep the codebase for that specific function/class/constant
   - Note the exact file and line where each usage occurs
   - Determine if the project uses the changed parameter, default, or behavior

4. **Check subdependency usage:**
   - Grep the lock file for the library name to see if other packages depend on it
   - If the library is only a subdependency (not directly imported), note this — the risk shifts to compatibility with the parent package

5. **Detect unused libraries:**
   - If zero direct imports and zero configuration references are found, flag as **potentially unused**
   - Verify by checking if it's pulled in as a transitive dependency of another package
   - If truly unused: recommend removal from the manifest rather than upgrading

---

## Phase 3: Risk Assessment

**Goal:** Classify upgrade risk based on the intersection of changes and actual usage.

**Risk Levels:**

| Level | Criteria |
|-------|----------|
| **Safe** | Patch/minor with no breaking changes touching APIs in use. Changelog is clear and benign. |
| **Low Risk** | Minor version with new features/deprecations, but none affect usage. Or patch with behavioral change in code paths not exercised. |
| **Medium Risk** | Breaking changes exist but do not affect current usage patterns. OR behavioral changes in APIs in use but with low impact. Requires careful review. |
| **High Risk** | Breaking changes directly affect APIs/patterns in use. Code changes required before or after upgrade. |
| **Critical** | Major version bump affecting core functionality heavily depended on (e.g., the web framework, ORM, or HTTP client). Requires a migration plan, not just a PR merge. |

**Risk modifiers:**
- Dev-only dependency: Lower the risk one level — breakage only affects CI/local dev
- Library with comprehensive test coverage in the codebase: Lower risk — tests will catch issues
- Library touching auth/security/crypto: Raise risk awareness — even "safe" upgrades warrant extra scrutiny
- Large version jump (skipping multiple minors): Raise risk — cumulative changes compound

---

## Phase 4: Produce Report

Output a structured report in this exact format:

```markdown
## <library>: <current_version> -> <target_version>

**PR:** #<number> (if applicable)
**Bump type:** major | minor | patch
**Dependency group:** production | dev-only
**Risk level:** Safe | Low Risk | Medium Risk | High Risk | Critical

### Changelog Summary
<Concise summary of what changed between versions. Include version-by-version breakdown if multiple versions are spanned.>

### Breaking Changes
<List each breaking change. If none, state "None identified.">

### Usage in This Codebase
<Describe how the project uses this library: which modules import it, what APIs it calls, how it's configured. Include file paths.>

### Impact Analysis
<For each breaking change, state whether it affects usage and why/why not. Be specific — cite the exact code paths.>

### Unused Library Check
<State whether the library appears actively used, only used as a subdependency, or potentially unused entirely.>

### Recommendation
<One of:>
- **Merge as-is**: Safe to merge without code changes.
- **Merge after verification**: Run tests to confirm, but no code changes expected.
- **Merge with code changes**: List specific changes needed (file:line, what to change).
- **Do not merge — needs migration plan**: Explain why and what the plan should cover.
- **Remove library**: If unused, recommend removal instead of upgrade.

### Action Items
<Numbered list of concrete actions, if any. Empty if recommendation is "Merge as-is".>
```

---

## Guidelines

- **Never guess.** If you cannot find the changelog, say so and fall back to source code inspection. If you cannot determine usage, say so.
- **Be specific.** "This might break something" is useless. "The `verify` parameter default changed from `True` to `False` in `requests.get()`, and the project calls `requests.get()` without explicit `verify=` in `src/services/client.py:42`" is useful.
- **Check everything.** Even if a change looks harmless, verify against the code. Assumptions cause incidents.
- **Dev dependencies matter less** but still matter — broken CI blocks everyone.
- **Transitive effects are real.** If `library-A` upgrades and depends on `library-B` which is also pinned, flag potential version conflicts.
- **When in doubt, raise the risk level.** It's better to flag a false positive than miss a real issue.
