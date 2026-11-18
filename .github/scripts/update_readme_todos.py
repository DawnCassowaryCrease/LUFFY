#!/usr/bin/env python3
"""Update the Complete TODO List in README.md from main..dev Python changes."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import List, Tuple

REPO = Path(os.environ.get("GITHUB_WORKSPACE", ".")).resolve()
README_PATH = REPO / "README.md"
MAIN_REF = os.environ.get("MAIN_REF", "origin/main")
HEAD_REF = os.environ.get("HEAD_REF", "HEAD")
WORKFLOW_PATH = REPO / ".github/workflows/update-todo-readme.yml"
SELF_PATH = REPO / ".github/scripts/update_readme_todos.py"

HEADING_RE = re.compile(r"^###\s+.*Complete TODO List\s*$")
ENTRY_RE = re.compile(
    r"^- \[ \] \*\*(?P<path>.+?):(?P<line>\d+)\*\* - (?P<desc>.*)$"
)


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO, text=True, capture_output=True, check=True
    )
    return result.stdout


def changed_python_files() -> List[str]:
    raw = git("diff", "--name-only", f"{MAIN_REF}...{HEAD_REF}")
    files = sorted(
        {
            line.strip().replace("\\", "/")
            for line in raw.splitlines()
            if line.strip().endswith(".py")
        }
    )
    print("Changed Python files:", files)
    return files


def extract_todos(rel_path: str) -> List[Tuple[int, str]]:
    path = REPO / rel_path
    if not path.exists():
        print(f"  {rel_path} is absent in head; all entries will be removed")
        return []

    text = path.read_text(encoding="utf-8")
    found: List[Tuple[int, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        pos = line.find("TODO")
        if pos < 0:
            continue
        rest = line[pos + 4 :]
        # Normalize the common "TODO:" prefix. Do not strip the colon that
        # belongs to a parenthesized author, e.g. TODO(sgm): message.
        rest = re.sub(r"^\s*:\s?", "", rest, count=1)
        description = rest.strip()
        found.append((line_no, description))
    print(f"  Extracted {len(found)} TODO(s) from {rel_path}")
    for line_no, description in found:
        print(f"    {line_no}: {description}")
    return found


def make_entry(rel_path: str, line_no: int, description: str) -> str:
    return f"- [ ] **{rel_path}:{line_no}** - {description}"


def main() -> None:
    changed_files = changed_python_files()
    readme = README_PATH.read_text(encoding="utf-8")
    original_had_final_newline = readme.endswith("\n")
    lines = readme.splitlines()

    heading_index = next(
        (i for i, line in enumerate(lines) if HEADING_RE.match(line)), None
    )
    if heading_index is None:
        raise RuntimeError("Could not find '### ... Complete TODO List' heading")

    section_end = next(
        (
            i
            for i in range(heading_index + 1, len(lines))
            if re.match(r"^##\s", lines[i])
        ),
        len(lines),
    )

    retained: List[Tuple[str, int, str]] = []
    baseline_count = 0
    unknown_section_lines: List[str] = []
    for line in lines[heading_index + 1 : section_end]:
        if not line.strip():
            continue
        match = ENTRY_RE.match(line)
        if not match:
            unknown_section_lines.append(line)
            continue
        baseline_count += 1
        path = match.group("path")
        if path in changed_files:
            continue
        retained.append((path, int(match.group("line")), line))

    if unknown_section_lines:
        details = "\n".join(repr(line) for line in unknown_section_lines)
        raise RuntimeError(f"Unexpected non-entry lines in TODO section:\n{details}")

    updated: List[Tuple[str, int, str]] = list(retained)
    extracted_total = 0
    for rel_path in changed_files:
        for line_no, description in extract_todos(rel_path):
            extracted_total += 1
            updated.append(
                (rel_path, line_no, make_entry(rel_path, line_no, description))
            )

    # Required order: path lexicographic, then line number ascending.
    updated.sort(key=lambda item: (item[0], item[1]))

    # Validate every final line parses and is sorted.
    previous_key = None
    final_entries: List[str] = []
    for path, line_no, raw_entry in updated:
        match = ENTRY_RE.match(raw_entry)
        if not match:
            raise RuntimeError(f"Generated invalid entry: {raw_entry!r}")
        if match.group("path") != path or int(match.group("line")) != line_no:
            raise RuntimeError(f"Entry key mismatch: {raw_entry!r}")
        key = (path, line_no)
        if previous_key is not None and key < previous_key:
            raise RuntimeError(f"Entries are not sorted at {key} after {previous_key}")
        previous_key = key
        final_entries.append(raw_entry)

    heading_line = lines[heading_index]
    new_lines = [
        *lines[:heading_index],
        heading_line,
        "",
        *final_entries,
        "",
        *lines[section_end:],
    ]
    new_readme = "\n".join(new_lines)
    if original_had_final_newline and not new_readme.endswith("\n"):
        new_readme += "\n"

    if new_readme == readme:
        print("README content already up to date; no README diff.")
    else:
        README_PATH.write_text(new_readme, encoding="utf-8")

    print(f"Baseline entries parsed: {baseline_count}")
    print(f"Retained unchanged-file entries: {len(retained)}")
    print(f"Extracted changed-file entries: {extracted_total}")
    print(f"Final TODO entries: {len(final_entries)}")

    # Remove temporary automation files so the final tree only changes README.
    for temp_path in (SELF_PATH, WORKFLOW_PATH):
        try:
            temp_path.unlink()
            print(f"Removed temporary file: {temp_path.relative_to(REPO)}")
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
