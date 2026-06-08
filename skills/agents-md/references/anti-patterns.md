# AGENTS.md Anti-Patterns

Common mistakes that degrade agent performance, and how to fix them.

## Table of Contents
1. [Vague Instructions](#vague-instructions)
2. [Over-Documentation](#over-documentation)
3. [Stale Commands](#stale-commands)
4. [Missing Fast Feedback Loop](#missing-fast-feedback-loop)
5. [Credentials & Secrets](#credentials--secrets)
6. [Monorepo Confusion](#monorepo-confusion)
7. [Wrong Scope](#wrong-scope)
8. [Missing Permission Boundaries](#missing-permission-boundaries)

---

## Vague Instructions

**Problem:** Instructions that require human interpretation fail silently — the agent guesses.

| Anti-pattern | Fix |
|---|---|
| "Run tests properly" | `cd src && python manage.py test myapp.tests` |
| "Build it carefully" | `uv run python -m build --wheel` |
| "Use the usual package manager" | "This project uses `uv`, not pip. Always run `uv sync` after changing dependencies." |
| "Follow our coding standards" | "Black 24 (120-char), isort. See `src/myapp/views/login.py` as the canonical style example." |
| "Don't use deprecated APIs" | "Avoid `src/myapp/legacy_views/` — these are legacy. Use `src/myapp/views/` for all new code." |
| "React project" | "React 18.3 + TypeScript 5.4, Vite 5, Tailwind CSS 3.4" |

---

## Over-Documentation

**Problem:** Files over 150 lines bury critical info and waste tokens on every request.

**Signs:**
- Complete API documentation in AGENTS.md
- Long explanations of how the framework works (agents already know Django/React)
- Copying content from README.md verbatim
- Documenting every file and directory

**Fix:** Reference separate docs instead:

```markdown
# Bad
## Architecture
The auth module is in src/myapp/views/. It contains login.py which handles password
login, passwordless.py which handles magic links, mfa/ which is a directory containing
totp.py for TOTP authentication, webauthn.py for passkeys, push.py for push...
[50 more lines]

# Good
## Architecture
API views: `src/myapp/views/` (organized by feature)
Models: `src/myapp/models/`
See `docs/architecture.md` for full module breakdown.
```

**Rule of thumb:** If describing something agents can discover by reading the code in 30 seconds, skip it. Document decisions and conventions that aren't obvious from the code.

---

## Stale Commands

**Problem:** Wrong commands are worse than no commands. Agents will follow them and fail silently or waste time debugging.

**Signs:**
- Commands that reference moved/renamed scripts
- Old package manager commands (e.g., `pip install` when project switched to `uv`)
- Build commands missing required environment variables

**Fix:**
- Treat AGENTS.md as code: update it in the same PR when commands change
- Add it to CI checks if possible
- Test commands by copy-pasting them in a fresh terminal

**Verification prompt:** Ask an agent "Set up my dev environment using AGENTS.md" — if it fails, fix the instructions.

---

## Missing Fast Feedback Loop

**Problem:** Only documenting full builds forces agents to run slow commands for small changes, burning tokens and time.

```markdown
# Bad — only full suite
## Testing
Run all tests: `make test`

# Good — fast commands first
## Testing
Single test (fast — use for iteration):
`cd src && python manage.py test myapp.tests.test_login.LoginTestCase.test_password_login`

Lint one file:
`cd src && pylint myapp/views/login.py`

Full suite (slow — only when explicitly requested):
`make test`
```

**Rule:** Always provide a per-file or single-test command. Full builds should be opt-in.

---

## Credentials & Secrets

**Problem:** Embedding actual values in AGENTS.md can leak secrets via logs, model context, or version control.

**Never include:**
- API keys, tokens, passwords
- Database connection strings with credentials
- AWS access keys or secret keys
- OAuth client secrets
- Internal hostnames or IPs with auth

**Instead, describe where they live:**

```markdown
# Bad
## Config
DATABASE_URL=postgres://admin:s3cr3t@db.internal:5432/myapp

# Good
## Config
Secrets live in AWS Secrets Manager under `/myapp/{env}/`.
Use `aws secretsmanager get-secret-value --secret-id /myapp/local/db` to get local DB creds.
Local dev: `manage.py` defaults to `myapp.settings.test`. Override via `.env` or env var as needed.
```

---

## Monorepo Confusion

**Problem:** A single root AGENTS.md trying to cover 5+ packages becomes bloated and context-irrelevant.

**Anti-pattern:**
```markdown
# Bad — one 400-line root AGENTS.md
## Frontend Testing
cd packages/web && pnpm test

## Backend Testing
cd packages/api && pytest

## Mobile Testing
cd packages/mobile && flutter test
[300 more lines per package...]
```

**Fix — nested files with clear scope:**
```
/AGENTS.md                 ← ≤50 lines: workspace nav, shared tools, global conventions
/packages/api/AGENTS.md   ← API-specific commands and patterns
/packages/web/AGENTS.md   ← Frontend-specific commands and patterns
/packages/mobile/AGENTS.md ← Mobile-specific commands and patterns
```

Root `AGENTS.md` for a monorepo:
```markdown
## Workspace Navigation
Each package has its own AGENTS.md with package-specific commands.
Run commands from the package root, not workspace root.

Shared tooling:
- Changesets for versioning: `pnpm changeset`
- Lint all: `pnpm run lint` (slow — prefer per-package)
```

---

## Wrong Scope

**Problem:** Including task-specific or session-specific content in AGENTS.md wastes tokens on unrelated tasks.

**Ask before adding anything:** "Will every agent working on every task need this?"

| Doesn't belong in AGENTS.md | Where it belongs |
|---|---|
| Feature-specific business logic | Inline in a ticket/prompt |
| Complete database schema | `references/schema.md` (linked from AGENTS.md) |
| API endpoint documentation | `docs/api.md` (linked from AGENTS.md) |
| "Currently working on the login refactor" | Conversation context |
| How Django's ORM works | Don't document — agents already know |

---

## Missing Permission Boundaries

**Problem:** Without explicit boundaries, agents guess — sometimes destructively.

**Anti-pattern:** No permissions section → agent deletes a file without asking, or commits directly to main.

**Fix — always include explicit three-tier permissions:**

```markdown
## Permissions

✅ Always:
- Read any file
- Run tests, lint, typecheck on individual files
- Create new files in appropriate directories

⚠️ Ask first:
- Install or remove packages
- Run database migrations
- Push branches or open PRs
- Run any command that modifies shared state

🚫 Never:
- Commit secrets or credentials
- Force push
- Delete files without explicit instruction
- Run `terraform apply` or infrastructure changes
- Modify production environment configs
```
