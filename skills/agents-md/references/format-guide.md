# AGENTS.md Format Guide

## Table of Contents
1. [File Placement & Discovery](#file-placement--discovery)
2. [Section Templates](#section-templates)
3. [Good vs Bad Examples](#good-vs-bad-examples)
4. [Stack-Specific Patterns](#stack-specific-patterns)

---

## File Placement & Discovery

**Filename**: Must be `AGENTS.md` (uppercase). Some tools also recognize `CLAUDE.md`.

**Discovery hierarchy** (most tools follow this):
1. `~/.config/AGENTS.md` or `~/.codex/AGENTS.md` — global defaults
2. Repo root `AGENTS.md` — project norms
3. Subdirectory `AGENTS.md` — overrides for that subtree (nearest wins)

**Monorepo layout example:**
```
/AGENTS.md               ← workspace-level: shared tools, monorepo nav
/packages/api/AGENTS.md  ← service-level: API-specific stack and commands
/packages/web/AGENTS.md  ← service-level: frontend-specific patterns
```

---

## Section Templates

### Project (Required)

One sentence. Name, purpose, tech stack with versions.

```markdown
## Project

Django 4.2 REST API (Python 3.12, PostgreSQL 15, Redis 7).
Handles accounts, billing, and notifications for the customer portal.
```

### Setup

Include only non-obvious steps. Skip "install git."

```markdown
## Setup

```bash
brew install uv libxmlsec1 swig libmagic openssl postgresql@15
uv sync --group dev
pre-commit install
docker compose up -d
cd src && uv run python manage.py migrate
```
```

### Build & Test

**Structure**: fast (file-scoped) first, then full suite.

```markdown
## Build & Test

Single file (fast — use these for iteration):
```bash
# Lint one file
cd src && pylint myapp/views/login.py

# Type-check one file
cd src && mypy myapp/views/login.py

# Run one test
cd src && python manage.py test myapp.tests.test_login.LoginTestCase.test_password_login
```

Full suite (slow — only when explicitly asked):
```bash
make test           # all tests
make test-api       # API tests only
```
```

### Code Style

Reference real files, not just rules.

```markdown
## Code Style

- Black 24 (120-char line length), isort for imports
- Django REST Framework patterns throughout — see `src/myapp/views/login.py` as a canonical example
- Prefer explicit imports; avoid `from module import *`
- New API views: subclass `APIView`, not `GenericAPIView` unless pagination needed
- Don't use `f-strings` for log messages — use `%s` formatting
```

### Architecture

Tell agents where to look and what to avoid.

```markdown
## Architecture

Key directories:
- `src/myapp/views/` — REST API endpoints (entry points for most features)
- `src/myapp/models/` — Django models (User, Account, Subscription)
- `src/myapp/admin/` — Admin site (separate service, different settings)
- `src/shared_lib/` — Shared utilities (do not modify without cross-team review)

Entry point: `src/myapp/urls.py`
Admin entry point: `src/myapp/admin/urls.py`

Legacy code to avoid copying: `src/myapp/legacy_views/` (old non-DRF views, being phased out)
```

### Permissions

Use three tiers. Be explicit.

```markdown
## Permissions

✅ Always allowed:
- Read any file in the repo
- Run single-file lint, typecheck, format
- Run specific test files

⚠️ Ask before:
- Installing or removing packages (`uv add`, `pip install`)
- Running `git commit`, `git push`, `git reset`
- Creating or deleting files

🚫 Never:
- Commit or log secrets, API keys, credentials
- Modify files in `deploy/prod/` without explicit instruction
- Run `terraform apply` or database migrations without confirmation
- Delete files or branches
```

### Git Workflow (optional but high-value)

```markdown
## Git Workflow

Branch naming: `<type>/<ticket>-<short-description>` (e.g., `feat/PROJ-1234-add-passkey-login`)
Commit style: Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`)
PR title: same format as commit message

Before opening PR:
```bash
pre-commit run --all-files
make test-api
```
```

---

## Good vs Bad Examples

### Commands

| Bad | Good |
|-----|------|
| "Run the tests" | `cd src && python manage.py test` |
| "Build the project carefully" | `uv run python -m build` |
| "Deploy to staging" | `aws ecs update-service --cluster staging --service web-api --force-new-deployment` |
| "Use the usual linter" | `cd src && pylint myapp/ --rcfile=../.pylintrc` |

### Stack Description

| Bad | Good |
|-----|------|
| "React project" | "React 18 + TypeScript 5, Vite, Tailwind CSS 3" |
| "Python backend" | "Django 4.2, Python 3.12, DRF 3.14" |
| "Uses a database" | "PostgreSQL 15 (primary) + Redis 7 (cache/sessions)" |

### Code Style

| Bad | Good |
|-----|------|
| "Write clean code" | "Black 24, 120-char lines. See `src/myapp/views/login.py` for style." |
| "Follow our conventions" | "Use `APIView` not `GenericAPIView`. No `f-strings` in log messages." |
| "Don't use legacy patterns" | "Avoid `src/myapp/legacy_views/` — use `src/myapp/views/` instead." |

---

## Stack-Specific Patterns

### Python / Django

```markdown
## Build & Test

```bash
# Single test
cd src && python manage.py test myapp.tests.test_login.LoginTestCase.test_password_login

# Admin tests (different settings)
cd src && APP_SERVICE=admin python manage.py test myapp.admin.tests.test_staff.StaffTestCase

# Coverage
cd src && coverage run manage.py test && coverage html
```

Package manager: uv (`uv sync`, `uv add <pkg>`, `uv run <cmd>`)
```

### Node.js / TypeScript

```markdown
## Build & Test

Package manager: pnpm (not npm or yarn)

```bash
pnpm install           # install deps
pnpm run typecheck     # type-check only (fast)
pnpm run lint:file src/api/login.ts   # lint one file
pnpm test -- --testPathPattern=login  # single test file
pnpm run build         # full build (slow — only when asked)
```
```

### Monorepo (Turborepo / nx)

```markdown
## Setup

Navigate packages with `cd packages/<name>`. Run commands from package root, not workspace root.

Workspace tools (run from root):
```bash
turbo run build --filter=@acme/api  # build one package
turbo run test --filter=@acme/api   # test one package
```
```

### Terraform

```markdown
## Infrastructure

```bash
cd infra/
terraform init
terraform validate
terraform plan -var-file=environments/staging.tfvars
# terraform apply — ALWAYS ask before running
```

Tag all resources. State is locked in S3 + DynamoDB.
Never hardcode region — use `var.aws_region`.
```
