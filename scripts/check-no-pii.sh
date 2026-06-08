#!/usr/bin/env bash
# Pre-publish PII guard — catches the free-form leaks that a secret scanner
# (gitleaks) misses: corporate emails, absolute home paths, the maintainer's
# username. Enforces the AGENTS.md "Pre-publish safety checklist" automatically.
#
# Runs as a pre-commit hook; pre-commit passes the staged files as arguments.
# Standalone usage: scripts/check-no-pii.sh <file>...
set -uo pipefail

# Governance docs legitimately quote the forbidden patterns AS the rules — don't
# scan them, or the guard would flag its own rulebook. The guard script itself
# is excluded for the same reason.
EXCLUDE_REGEX='^(AGENTS\.md|CLAUDE\.md|CONTRIBUTING\.md|scripts/check-no-pii\.sh|\.pre-commit-config\.yaml)$'

# Forbidden identifiers (AGENTS.md pre-publish checklist):
#   @ui.com        corporate email — schwannden@gmail.com is the only allowed one
#   /Users/        absolute macOS home path leaking a username
#   /home/<name>/  absolute Linux home path leaking a username
#   schwanndenkuo  the maintainer's OS username
PATTERN='@ui\.com|/Users/|/home/[a-z][a-z0-9_-]*|schwanndenkuo'

status=0
report=""
for f in "$@"; do
  [[ "$f" =~ $EXCLUDE_REGEX ]] && continue
  [ -f "$f" ] || continue
  # Skip binary files (grep -I prints nothing and exits 1 for binary).
  grep -Iq . "$f" 2>/dev/null || continue
  if matches=$(grep -nE "$PATTERN" "$f" 2>/dev/null); then
    report+=$'\n'"  ${f}:"$'\n'"$(printf '%s\n' "$matches" | sed 's/^/    /')"
    status=1
  fi
done

if [ "$status" -ne 0 ]; then
  echo "✗ pre-publish PII guard found forbidden identifiers:"
  echo "$report"
  echo
  echo "Fix before committing: use schwannden@gmail.com for any email, and replace"
  echo "absolute home paths with ~/ or a <placeholder>. See AGENTS.md pre-publish checklist."
  exit 1
fi
exit 0
