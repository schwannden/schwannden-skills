---
description: "Comprehensive PR review using specialized agents"
argument-hint: "[review-aspects]"
allowed-tools: ["Bash", "Glob", "Grep", "Read", "Task"]
---

# Comprehensive PR Review

Run a comprehensive pull request review using multiple specialized agents, each focusing on a different aspect of code quality.

**Review Aspects (optional):** "$ARGUMENTS"

## Review Workflow:

1. **Determine Review Scope**
   - Check git status to identify changed files.
   - Parse arguments to see if the user requested specific review aspects.
   - Default: run all applicable reviews.

2. **Available Review Aspects:**

   - **comments** — Analyze code comment / docstring / doc accuracy and maintainability
   - **tests** — Review test coverage quality and completeness
   - **errors** — Check error handling for silent failures
   - **types** — Analyze type / model / schema design and invariants (if new types added)
   - **code** — General code review for correctness, security, and project guidelines
   - **simplify** — Simplify code for clarity and maintainability
   - **all** — Run all applicable reviews (default)

3. **Identify Changed Files**
   - Run `git diff --name-only` to see modified files (compare against the base branch when reviewing a branch/PR).
   - Check if a PR already exists: `gh pr view`.
   - Identify file types and what reviews apply.

4. **Determine Applicable Reviews**

   Based on the changes:
   - **Always applicable**: `code-reviewer` (general quality, correctness, security).
   - **If test files changed**: `pr-test-analyzer`.
   - **If comments / docs / API specs added or changed**: `doc-analyzer`.
   - **If error handling changed**: `silent-failure-hunter`.
   - **If types / models / schemas added or modified**: `type-design-analyzer`.
   - **After passing review**: `code-simplifier` (polish and refine).

5. **Launch Review Agents**

   **Sequential approach** (one at a time):
   - Easier to understand and act on.
   - Each report is complete before the next.
   - Good for interactive review.

   **Parallel approach** (user can request, e.g. `all parallel`):
   - Launch all applicable agents simultaneously via the `Task` tool.
   - Faster for comprehensive review.
   - Results come back together.

   Dispatch each agent by its name as the `subagent_type`. The orchestrator owns the agent matrix — agents must not invoke one another.

6. **Aggregate Results**

   After agents complete, summarize:
   - **Critical Issues** (must fix before merge)
   - **Important Issues** (should fix)
   - **Suggestions** (nice to have)
   - **Positive Observations** (what's good)

7. **Provide Action Plan**

   Organize findings:
   ```markdown
   # PR Review Summary

   ## Critical Issues (X found)
   - [agent-name]: Issue description [file:line]

   ## Important Issues (X found)
   - [agent-name]: Issue description [file:line]

   ## Suggestions (X found)
   - [agent-name]: Suggestion [file:line]

   ## Strengths
   - What's well-done in this PR

   ## Recommended Action
   1. Fix critical issues first
   2. Address important issues
   3. Consider suggestions
   4. Re-run review after fixes
   ```

## Usage Examples:

**Full review (default):**
```
/review-pr
```

**Specific aspects:**
```
/review-pr tests errors
# Reviews only test coverage and error handling

/review-pr comments
# Reviews only code comments

/review-pr simplify
# Simplifies code after passing review
```

**Parallel review:**
```
/review-pr all parallel
# Launches all applicable agents in parallel
```

## Agent Descriptions:

**doc-analyzer**:
- Verifies comment / docstring accuracy vs code
- Identifies comment rot and stale docs
- Checks documentation and API-spec completeness/consistency

**pr-test-analyzer**:
- Reviews behavioral test coverage
- Identifies critical gaps (security, auth, error paths)
- Evaluates test quality and flags brittle tests

**silent-failure-hunter**:
- Finds silent failures
- Reviews catch/except blocks and fallbacks
- Checks error logging and propagation

**type-design-analyzer**:
- Analyzes type / model / schema encapsulation
- Reviews invariant expression and enforcement
- Rates type design quality (1–10 across four axes)

**code-reviewer**:
- Checks `AGENTS.md` / `CLAUDE.md` convention compliance
- Detects bugs, correctness issues, and security problems
- Reviews general code quality (confidence-filtered)

**code-simplifier**:
- Simplifies complex code
- Improves clarity and readability
- Applies project standards while preserving functionality

## Tips:

- **Run early**: before creating the PR, not after.
- **Focus on changes**: agents analyze the diff by default.
- **Address critical first**: fix high-priority issues before lower priority.
- **Re-run after fixes**: verify issues are resolved.
- **Use specific reviews**: target specific aspects when you know the concern.

## Notes:

- Agents run autonomously and return detailed reports.
- Each agent focuses on its specialty for deep analysis.
- Results are actionable with specific `file:line` references.
- All agents are available in the `/agents` list once the plugin is installed.
