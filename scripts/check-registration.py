#!/usr/bin/env python3
"""Validate that every skill and plugin is registered consistently.

This enforces the repo invariant that a skill/plugin change keeps four things
in lockstep (see AGENTS.md § "The registration invariant"):

  1. skills/<name>/SKILL.md           — folder exists, frontmatter `name` == folder
  2. .claude-plugin/marketplace.json  — listed in exactly one themed plugin's `skills`
  3. README.md                        — has a catalog row mentioning the skill
  4. plugins/<name>/                   — registered with its own isolated `source`

Run from anywhere:  python3 scripts/check-registration.py
Exits 0 if consistent, 1 (with a report) if anything has drifted.
No third-party dependencies — standard library only.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / "skills"
PLUGINS_DIR = REPO / "plugins"
MANIFEST = REPO / ".claude-plugin" / "marketplace.json"
README = REPO / "README.md"

# Frontmatter rules from AGENTS.md § "How to author a new skill".
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")  # lowercase, single hyphens
NAME_MAX = 64
DESC_MAX = 1024
BODY_MAX_LINES = 500
FORBIDDEN_NAME_WORDS = ("claude", "anthropic")

errors: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


def parse_frontmatter(skill_md: Path) -> tuple[dict[str, str], int]:
    """Return ({frontmatter key: value}, body line count) for a SKILL.md.

    Minimal single-line `key: value` parser (no PyYAML dependency) — enough for
    SKILL.md, whose frontmatter only carries `name` and `description`. Strips one
    layer of matching surrounding quotes. Returns ({}, 0) if the `---` fences are
    missing so the caller can report it.
    """
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, 0
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, 0

    fm: dict[str, str] = {}
    for line in lines[1:end]:
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fm[key] = value

    return fm, len(lines[end + 1:])


def check_frontmatter(name: str, skill_md: Path) -> None:
    """Validate a skill's frontmatter against the AGENTS.md hard rules."""
    fm, body_lines = parse_frontmatter(skill_md)
    if not fm:
        fail(f"skills/{name}/SKILL.md has no parseable `---` frontmatter block")
        return

    fm_name = fm.get("name")
    if fm_name is None:
        fail(f"skills/{name}/SKILL.md has no `name:` in frontmatter")
    else:
        if fm_name != name:
            fail(f"skills/{name}: frontmatter name '{fm_name}' != folder name '{name}'")
        if len(fm_name) > NAME_MAX:
            fail(f"skills/{name}: name exceeds {NAME_MAX} chars")
        if not NAME_RE.match(fm_name):
            fail(f"skills/{name}: name '{fm_name}' must be lowercase a-z0-9 with single hyphens")
        for word in FORBIDDEN_NAME_WORDS:
            if word in fm_name.lower():
                fail(f"skills/{name}: name must not contain '{word}'")

    desc = fm.get("description")
    if not desc:
        fail(f"skills/{name}/SKILL.md frontmatter has no `description:`")
    elif len(desc) > DESC_MAX:
        fail(f"skills/{name}: description is {len(desc)} chars (max {DESC_MAX})")

    # AGENTS.md waives the 500-line body cap for vendored skills (preserve the
    # clean upstream copy).
    vendored = (SKILLS_DIR / name / "VENDORED.md").is_file()
    if not vendored and body_lines > BODY_MAX_LINES:
        fail(f"skills/{name}/SKILL.md body is {body_lines} lines (max {BODY_MAX_LINES})")


def load_manifest() -> dict:
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        fail(f"marketplace.json is unreadable/invalid JSON: {e}")
        return {}


def main() -> int:
    manifest = load_manifest()
    plugins = manifest.get("plugins", [])

    # --- collect registered skills (from themed plugins, source "./") ----------
    registered_skills: dict[str, list[str]] = {}  # skill -> [plugin names]
    registered_plugin_sources: set[str] = set()  # "./plugins/<name>"
    for p in plugins:
        src = p.get("source", "")
        if src == "./":
            for s in p.get("skills", []):
                name = s.removeprefix("./skills/").strip("/")
                registered_skills.setdefault(name, []).append(p.get("name", "?"))
        elif src.startswith("./plugins/"):
            registered_plugin_sources.add(src.strip("/").removeprefix("./"))

    # --- disk truth -------------------------------------------------------------
    disk_skills = sorted(
        d.name for d in SKILLS_DIR.iterdir() if d.is_dir()
    ) if SKILLS_DIR.is_dir() else []
    disk_plugins = sorted(
        d.name for d in PLUGINS_DIR.iterdir() if d.is_dir()
    ) if PLUGINS_DIR.is_dir() else []

    readme = README.read_text(encoding="utf-8") if README.is_file() else ""

    # --- skill checks -----------------------------------------------------------
    for name in disk_skills:
        skill_md = SKILLS_DIR / name / "SKILL.md"
        if not skill_md.is_file():
            fail(f"skills/{name}/ has no SKILL.md")
            continue
        check_frontmatter(name, skill_md)
        if name not in registered_skills:
            fail(f"skills/{name}/ is NOT registered in marketplace.json (no plugin lists it)")
        elif len(registered_skills[name]) > 1:
            fail(f"skills/{name}/ is registered in multiple plugins: {registered_skills[name]}")
        if not re.search(rf"\b{re.escape(name)}\b", readme):
            fail(f"skills/{name}/ has no catalog row in README.md")

    for name, where in registered_skills.items():
        if name not in disk_skills:
            fail(f"marketplace.json registers './skills/{name}' (in {where}) but skills/{name}/ does not exist")

    # --- plugin checks ----------------------------------------------------------
    for name in disk_plugins:
        manifest_json = PLUGINS_DIR / name / ".claude-plugin" / "plugin.json"
        if not manifest_json.is_file():
            fail(f"plugins/{name}/ has no .claude-plugin/plugin.json")
        else:
            try:
                json.loads(manifest_json.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                fail(f"plugins/{name}/.claude-plugin/plugin.json is invalid JSON: {e}")
        if f"plugins/{name}" not in registered_plugin_sources:
            fail(f"plugins/{name}/ is NOT registered in marketplace.json (no isolated source)")

    for src in registered_plugin_sources:
        name = src.removeprefix("plugins/")
        if name not in disk_plugins:
            fail(f"marketplace.json registers source './{src}' but plugins/{name}/ does not exist")

    # --- README catalog count line ("N skills across M themes") -----------------
    themed_count = sum(1 for p in plugins if p.get("source") == "./")
    m = re.search(r"(\d+)\s+skills?\s+across\s+(\d+)\s+themes", readme)
    if m:
        n_skills, n_themes = int(m.group(1)), int(m.group(2))
        if n_skills != len(disk_skills):
            fail(f"README.md says {n_skills} skills but {len(disk_skills)} are on disk")
        if n_themes != themed_count:
            fail(f"README.md says {n_themes} themes but marketplace.json has {themed_count} themed plugins")

    # --- report -----------------------------------------------------------------
    if errors:
        print(f"✗ registration check FAILED — {len(errors)} issue(s):\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(
        f"✓ registration consistent: {len(disk_skills)} skills, "
        f"{len(disk_plugins)} command/agent plugins, all linked in "
        f"marketplace.json + README.md."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
