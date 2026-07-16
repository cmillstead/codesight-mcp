"""Invariant: ToolSpec.untrusted must match the actual _meta.contentTrust a
tool emits at runtime.

Every read-only tool that is invokable against a single indexed repo (no
extra symbol_id / file_path / second-repo / URL / write args) is exercised
against a real fixture and its returned ``_meta.contentTrust`` is compared,
in both directions, to its registered ``ToolSpec.untrusted`` flag. Tools
that cannot be invoked this way are skipped with a documented reason --
never via a source-code scan.
"""

from codesight_mcp.tools.registry import load_all_specs

# Tools that cannot be exercised read-only against the shared single-symbol
# fixture, with the reason each is excluded. Never fall back to grepping
# source for these -- if one becomes invokable later, move it into the
# exercised set instead.
_SKIP_REASONS = {
    "invalidate_cache": "destructive -- would delete the fixture index needed by other invocations in this loop",
    "index_repo": "requires an external URL; write/indexing operation, not read-only against an existing fixture",
    "index_folder": "requires a filesystem path to index; write operation",
    "check_licenses": "requires repo_path (a project directory with lockfiles), not an indexed-repo id",
    "generate_sbom": "requires repo_path (a project directory with lockfiles), not an indexed-repo id",
    "compare_symbols": "requires base_repo and head_repo (two distinct indexed repos); fixture provides only one",
    "get_call_chain": "requires from_symbol and to_symbol (two distinct symbol_ids); fixture provides only one symbol",
    "get_callees": "requires a symbol_id",
    "get_callers": "requires a symbol_id",
    "get_changes": "requires repo_path (a git working directory) to run git diff, not an indexed-repo id -- same class as check_licenses/generate_sbom",
    "get_impact": "requires a symbol_id",
    "get_symbol_context": "requires a symbol_id",
    "get_symbols": "requires symbol_ids",
    "get_type_hierarchy": "requires a symbol_id",
    "get_file_outline": "requires a file_path",
    "get_imports": "requires a file",
    "get_diagram": "requires a diagram type",
    "get_usage_stats": "registered handler is a stub returning {'error': ...} at registry-load time; the real handler is wired later by server.py, not reachable via load_all_specs()",
    "search_references": "requires a query",
    "search_symbols": "requires a query",
    "search_text": "requires a query",
}


def _invoke_readonly(spec, python_index: dict, storage_path: str) -> dict | None:
    """Build args for a repo-only (or arg-less) tool and call its handler.

    Returns None for tools outside the exercised set (see _SKIP_REASONS).
    """
    if spec.name in _SKIP_REASONS:
        return None
    args: dict = {}
    if "repo" in spec.required_args:
        args["repo"] = f"{python_index['owner']}/{python_index['name']}"
    if spec.name == "get_symbol":
        # Real symbol_id from the fixture -- genuinely exercises get_symbol
        # instead of letting it fall through as a silent, undocumented skip.
        args["symbol_id"] = python_index["sym_id"]
    return spec.handler(args, storage_path)


def test_untrusted_flag_matches_actual_meta_trust(python_index, tmp_path):
    """Call each read-only tool against a real indexed fixture and compare
    result["_meta"]["contentTrust"] to ToolSpec.untrusted, both directions."""
    specs = load_all_specs()
    storage_path = str(tmp_path)
    exercised = []
    mismatches = []
    silently_dropped = []

    for name, spec in specs.items():
        if name in _SKIP_REASONS:
            continue  # documented reason -- see _SKIP_REASONS
        result = _invoke_readonly(spec, python_index, storage_path)
        if result is None:
            continue
        if "_meta" not in result:
            # A tool outside _SKIP_REASONS returned no _meta -- this is exactly
            # the silent, undocumented skip this test's docstring forbids.
            # Either exercise it for real or add a documented reason above.
            silently_dropped.append((name, result))
            continue
        exercised.append(name)
        meta_untrusted = result["_meta"].get("contentTrust") == "untrusted"
        if meta_untrusted != bool(spec.untrusted):
            mismatches.append((name, meta_untrusted, spec.untrusted))

    assert silently_dropped == [], (
        "Tools not in _SKIP_REASONS returned a result with no _meta -- "
        f"add a documented skip reason or fix the invocation: {silently_dropped}"
    )

    # Sanity: the 5 known-mismatched tools must actually have been exercised,
    # otherwise this test would pass vacuously.
    for expected_name in (
        "get_file_tree", "get_repo_outline", "lint_index", "list_repos", "verify",
    ):
        assert expected_name in exercised, (
            f"{expected_name} was not exercised -- test would pass vacuously"
        )

    # get_symbol is genuinely exercised via a real symbol_id from the fixture
    # (not silently skipped, which is the bug this test guards against).
    assert "get_symbol" in exercised, (
        "get_symbol was not exercised -- test would pass vacuously"
    )

    assert mismatches == [], f"_meta trust != ToolSpec.untrusted: {mismatches}"
