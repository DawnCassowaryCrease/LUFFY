#!/usr/bin/env python3
"""Remove temporary updater entries from README and validate the final list."""
from __future__ import annotations

import os
import re
from pathlib import Path

REPO = Path(os.environ.get("GITHUB_WORKSPACE", ".")).resolve()
README_PATH = REPO / "README.md"
BAD_PATH = ".github/scripts/update_readme_todos.py"
WORKFLOW_PATH = REPO / ".github/workflows/fix-todo-readme.yml"
SELF_PATH = REPO / ".github/scripts/fix_todo_readme.py"

HEADING_RE = re.compile(r"^###\s+.*Complete TODO List\s*$")
ENTRY_RE = re.compile(
    r"^- \[ \] \*\*(?P<path>.+?):(?P<line>\d+)\*\* - (?P<desc>.*)$"
)

EXPECTED = {
    "luffy/deepscaler/utils.py": [
        (45, "Add logging for API calls and errors"),
        (46, "Support batch processing for multiple prompts"),
        (47, "Add timeout configuration for API calls"),
        (107, "Implement Vertex AI initialization and authentication"),
        (108, "Configure safety settings for content generation"),
        (109, "Set up GenerativeModel with proper system instructions"),
        (110, "Implement retry logic with exponential backoff"),
        (111, "Add comprehensive error handling for API access issues"),
        (112, "Handle rate limiting and quota management"),
        (113, "Implement response validation and text extraction"),
        (114, "Add support for different generation configurations"),
    ],
    "luffy/verl/verl/protocol.py": [
        (114, "Optimize memory usage during tensor reshaping"),
        (115, "Add support for different tensor types and shapes"),
        (136, "Optimize tensor view operations for performance"),
        (137, "Add error handling for invalid batch dimensions"),
        (169, "(zhangchi.usc1992) add consistency check"),
        (265, "we can actually lift this restriction if needed"),
        (351, "(zhangchi.usc1992) whether to copy"),
    ],
}


def main() -> None:
    text = README_PATH.read_text(encoding="utf-8")
    raw_lines = text.splitlines(keepends=True)
    lines = text.splitlines()

    heading_indices = [i for i, line in enumerate(lines) if HEADING_RE.match(line)]
    if len(heading_indices) != 1:
        raise RuntimeError(f"Expected exactly one TODO heading, found {heading_indices}")
    heading_index = heading_indices[0]

    section_end = next(
        (
            i
            for i in range(heading_index + 1, len(lines))
            if re.match(r"^##\s", lines[i])
        ),
        len(lines),
    )

    bad_prefix = f"- [ ] **{BAD_PATH}:"
    output_lines = []
    removed = 0
    for index, line in enumerate(raw_lines):
        if (
            heading_index < index < section_end
            and line.strip().startswith(bad_prefix)
        ):
            removed += 1
            continue
        output_lines.append(line)

    if removed != 9:
        raise RuntimeError(f"Expected to remove 9 temporary entries, removed {removed}")

    cleaned = "".join(output_lines)
    if f"**{BAD_PATH}:" in cleaned:
        raise RuntimeError("A temporary TODO entry still remains")

    clean_lines = cleaned.splitlines()
    clean_heading = next(
        i for i, line in enumerate(clean_lines) if HEADING_RE.match(line)
    )
    clean_end = next(
        (
            i
            for i in range(clean_heading + 1, len(clean_lines))
            if re.match(r"^##\s", clean_lines[i])
        ),
        len(clean_lines),
    )

    entries = []
    for line in clean_lines[clean_heading + 1 : clean_end]:
        if not line.strip():
            continue
        match = ENTRY_RE.match(line)
        if not match:
            raise RuntimeError(f"Non-entry line in TODO section: {line!r}")
        entries.append(
            (
                match.group("path"),
                int(match.group("line")),
                match.group("desc"),
                line,
            )
        )

    if len(entries) != 215:
        raise RuntimeError(f"Expected 215 final entries, found {len(entries)}")

    keys = [(path, line_no) for path, line_no, _, _ in entries]
    if keys != sorted(keys):
        raise RuntimeError("TODO entries are not lexicographically sorted")

    actual = {}
    for path, line_no, desc, _ in entries:
        actual.setdefault(path, []).append((line_no, desc))

    for path, expected_items in EXPECTED.items():
        if actual.get(path) != expected_items:
            raise RuntimeError(
                f"Mismatch for {path}:\nExpected: {expected_items}\nActual: {actual.get(path)}"
            )

    README_PATH.write_text(cleaned, encoding="utf-8")
    print(f"Removed {removed} temporary entries.")
    print(f"Validated {len(entries)} sorted TODO entries.")
    for path in EXPECTED:
        print(f"{path}: {len(EXPECTED[path])} entries validated")

    for temp_path in (SELF_PATH, WORKFLOW_PATH):
        try:
            temp_path.unlink()
            print(f"Removed temporary file: {temp_path.relative_to(REPO)}")
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
