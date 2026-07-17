"""Verify doc counts match running-code values; fail CI on drift."""

import re
import subprocess
import sys
from pathlib import Path

from codesight_mcp.parser.languages import LANGUAGE_REGISTRY
from codesight_mcp.tools.registry import load_all_specs

_ROOT = Path(__file__).resolve().parent.parent
_DOCS = [
    "README.md",
    "docs/index.md",
    "docs/project-overview.md",
    "docs/architecture.md",
    "docs/development-guide.md",
    "docs/source-tree-analysis.md",
]
_STALE = ("2,495", "2495", "1,906", "1906")  # known-old test counts
_MARKER = "<!-- codesight:counts ops={ops} langs={langs} tests={tests} -->"

# Context-anchored patterns for visible counts. The denylist above only
# catches numbers that have gone stale since this script was written; these
# patterns catch a wrong visible number even when it was never on the
# denylist (e.g. the doc was updated to some other incorrect value). Each
# pattern requires the specific trailing/leading unit words so it never
# matches an unrelated integer (fan-in counts, percentages, LOC, etc.).
_TEST_COUNT_PATTERNS = (
    r"tests-(\d[\d,]*)-brightgreen",
    r"\*\*(\d[\d,]*)\s+tests\*\*",
    r"\*\*Tests:\*\*\s*(\d[\d,]*)\s+tests\b",
    r"Test count \| (\d[\d,]*) \|",
    r"\*\*Total\*\*\s*\|\s*\*\*(\d[\d,]*)\*\*",
    r"Run all tests \((\d[\d,]*) tests\)",
    r"Test suite \((\d[\d,]*) tests\)",
)
_OPS_COUNT_PATTERNS = (
    r"(\d+)\s+operations\b",
    r"(\d+)\s+separate tools\b",
    r"(\d+)-tool\b",
    r"(\d+)\s+MCP tools\b",
    r"(\d+)\s+MCP tool implementations\b",
    r"(\d+)\s+tools organized\b",
    r"(\d+)\s+tools with declarative\b",
    r"\((\d+) tools\)",
    r"(\d+)\s+tools for symbol retrieval\b",
)
_LANG_COUNT_PATTERNS = (
    r"(\d+)\s+languages\b",
    r"(\d+)\s+programming languages\b",
    r"(\d+)-language\b",
)


def _test_count() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd=_ROOT,
    )
    if result.returncode != 0:
        raise SystemExit(f"pytest --collect-only failed (exit {result.returncode}); cannot verify test count")
    match = re.search(r"(\d+)\s+tests?\s+collected", result.stdout)
    if not match:
        raise SystemExit("could not parse collected test count")
    return int(match.group(1))


def _check_visible_counts(rel: str, text: str, patterns: tuple[str, ...], live_value: int, label: str) -> list[str]:
    problems: list[str] = []
    for pattern in patterns:
        for found in re.findall(pattern, text):
            value = int(found.replace(",", ""))
            if value != live_value:
                problems.append(f"{rel}: stale visible {label} count {found!r} (expected {live_value})")
    return problems


def main() -> int:
    ops, langs, tests = len(load_all_specs()), len(LANGUAGE_REGISTRY), _test_count()
    marker = _MARKER.format(ops=ops, langs=langs, tests=tests)
    problems: list[str] = []
    for rel in _DOCS:
        text = (_ROOT / rel).read_text()
        for stale in _STALE:
            if stale in text:
                problems.append(f"{rel}: stale count literal {stale!r}")
        if marker not in text:
            problems.append(f"{rel}: missing/incorrect generated marker (expected: {marker})")
        problems.extend(_check_visible_counts(rel, text, _TEST_COUNT_PATTERNS, tests, "test"))
        problems.extend(_check_visible_counts(rel, text, _OPS_COUNT_PATTERNS, ops, "operations"))
        problems.extend(_check_visible_counts(rel, text, _LANG_COUNT_PATTERNS, langs, "language"))
    if problems:
        print("count drift:\n  " + "\n  ".join(problems))
        return 1
    print(f"counts OK: ops={ops} langs={langs} tests={tests}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
