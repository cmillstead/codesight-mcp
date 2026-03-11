"""Tests for compare_symbols tool (Task 7-8)."""

import pytest

from codesight_mcp.storage import IndexStore
from codesight_mcp.parser import Symbol
from codesight_mcp.tools.compare_symbols import compare_symbols


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_symbol(
    sym_id: str,
    name: str,
    kind: str = "function",
    file: str = "src/mod.py",
    signature: str = "def foo():",
    content_hash: str = "a" * 64,
) -> Symbol:
    """Build a minimal Symbol for testing."""
    return Symbol(
        id=sym_id,
        file=file,
        name=name,
        qualified_name=name,
        kind=kind,
        language="python",
        signature=signature,
        line=1, end_line=2,
        byte_offset=0, byte_length=10,
        content_hash=content_hash,
    )


def _save_repo(tmp_path, owner: str, name: str, symbols: list[Symbol]) -> None:
    """Save an indexed repo with the given symbols into tmp_path storage."""
    store = IndexStore(base_path=str(tmp_path))
    content_dir = tmp_path / f"{owner}__{name}"
    content_dir.mkdir(parents=True, exist_ok=True)
    (content_dir / "mod.py").write_text("# stub\n")
    store.save_index(
        owner=owner,
        name=name,
        source_files=["src/mod.py"],
        symbols=symbols,
        raw_files={"src/mod.py": "# stub\n"},
        languages={"python": len(symbols)},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def two_repos(tmp_path):
    """Create 'before' and 'after' repos with known differences.

    Symbols:
        - common_unchanged: same ID, same hash in both repos
        - common_modified:  same ID, different hash in head
        - only_in_base:     removed in head
        - only_in_head:     added in head
    """
    base_symbols = [
        _make_symbol(
            "src/mod.py::common_unchanged#function",
            name="common_unchanged",
            content_hash="a" * 64,
        ),
        _make_symbol(
            "src/mod.py::common_modified#function",
            name="common_modified",
            content_hash="b" * 64,
        ),
        _make_symbol(
            "src/mod.py::only_in_base#function",
            name="only_in_base",
            content_hash="c" * 64,
        ),
    ]

    head_symbols = [
        _make_symbol(
            "src/mod.py::common_unchanged#function",
            name="common_unchanged",
            content_hash="a" * 64,    # same hash -> unchanged
        ),
        _make_symbol(
            "src/mod.py::common_modified#function",
            name="common_modified",
            content_hash="d" * 64,    # different hash -> modified
        ),
        _make_symbol(
            "src/mod.py::only_in_head#function",
            name="only_in_head",
            content_hash="e" * 64,
        ),
    ]

    _save_repo(tmp_path, "local", "before", base_symbols)
    _save_repo(tmp_path, "local", "after", head_symbols)

    return str(tmp_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCompareSymbols:
    """Tests for compare_symbols tool."""

    def test_detects_added_symbols(self, two_repos):
        """Symbols present in head but not base appear in 'added'."""
        result = compare_symbols("local/before", "local/after", storage_path=two_repos)
        assert "error" not in result
        added_names = [_unwrap(e["name"]) for e in result["added"]]
        assert "only_in_head" in added_names

    def test_detects_removed_symbols(self, two_repos):
        """Symbols present in base but not head appear in 'removed'."""
        result = compare_symbols("local/before", "local/after", storage_path=two_repos)
        assert "error" not in result
        removed_names = [_unwrap(e["name"]) for e in result["removed"]]
        assert "only_in_base" in removed_names

    def test_detects_modified_symbols(self, two_repos):
        """Symbols with the same ID but different content_hash appear in 'modified'."""
        result = compare_symbols("local/before", "local/after", storage_path=two_repos)
        assert "error" not in result
        modified_names = [_unwrap(e["name"]) for e in result["modified"]]
        assert "common_modified" in modified_names

    def test_unchanged_symbols_not_in_any_list(self, two_repos):
        """Symbols with same ID and same content_hash are not in added/removed/modified."""
        result = compare_symbols("local/before", "local/after", storage_path=two_repos)
        assert "error" not in result

        all_names = (
            [_unwrap(e["name"]) for e in result["added"]]
            + [_unwrap(e["name"]) for e in result["removed"]]
            + [_unwrap(e["name"]) for e in result["modified"]]
        )
        assert "common_unchanged" not in all_names

    def test_summary_counts_are_correct(self, two_repos):
        """Summary counts match the actual list lengths."""
        result = compare_symbols("local/before", "local/after", storage_path=two_repos)
        assert "error" not in result

        summary = result["summary"]
        assert summary["added"] == len(result["added"])
        assert summary["removed"] == len(result["removed"])
        assert summary["modified"] == len(result["modified"])

        # Exactly 1 of each in our fixture
        assert summary["added"] == 1
        assert summary["removed"] == 1
        assert summary["modified"] == 1
        assert summary["unchanged"] == 1

    def test_repo_not_found_returns_error(self, tmp_path):
        """Missing base or head repo returns an error dict."""
        result = compare_symbols(
            "local/nonexistent_base",
            "local/nonexistent_head",
            storage_path=str(tmp_path),
        )
        assert "error" in result

    def test_missing_head_repo_returns_error(self, two_repos):
        """Missing head repo returns an error dict."""
        result = compare_symbols(
            "local/before",
            "local/does_not_exist",
            storage_path=two_repos,
        )
        assert "error" in result

    def test_has_meta_with_timing_ms(self, two_repos):
        """Response includes _meta envelope with timing_ms."""
        result = compare_symbols("local/before", "local/after", storage_path=two_repos)
        assert "_meta" in result
        assert "timing_ms" in result["_meta"]
        assert isinstance(result["_meta"]["timing_ms"], float)

    def test_meta_content_trust_is_untrusted(self, two_repos):
        """_meta contentTrust is 'untrusted' since symbol data is user-controlled."""
        result = compare_symbols("local/before", "local/after", storage_path=two_repos)
        assert result["_meta"]["contentTrust"] == "untrusted"

    def test_repo_labels_in_result(self, two_repos):
        """Result includes base_repo and head_repo labels."""
        result = compare_symbols("local/before", "local/after", storage_path=two_repos)
        assert result["base_repo"] == "local/before"
        assert result["head_repo"] == "local/after"

    def test_modified_entry_has_both_signatures(self, two_repos):
        """Modified entries include base_signature and head_signature fields."""
        result = compare_symbols("local/before", "local/after", storage_path=two_repos)
        assert result["modified"]
        entry = result["modified"][0]
        assert "base_signature" in entry
        assert "head_signature" in entry

    def test_added_entry_has_expected_fields(self, two_repos):
        """Added entries have id, name, kind, file, signature fields."""
        result = compare_symbols("local/before", "local/after", storage_path=two_repos)
        assert result["added"]
        entry = result["added"][0]
        assert "id" in entry
        assert "name" in entry
        assert "kind" in entry
        assert "file" in entry
        assert "signature" in entry

    def test_removed_entry_has_expected_fields(self, two_repos):
        """Removed entries have id, name, kind, file, signature fields."""
        result = compare_symbols("local/before", "local/after", storage_path=two_repos)
        assert result["removed"]
        entry = result["removed"][0]
        assert "id" in entry
        assert "name" in entry
        assert "kind" in entry
        assert "file" in entry
        assert "signature" in entry

    def test_identical_repos_no_changes(self, tmp_path):
        """Comparing identical repos yields zero added/removed/modified."""
        symbols = [
            _make_symbol("src/mod.py::foo#function", name="foo", content_hash="a" * 64),
            _make_symbol("src/mod.py::bar#function", name="bar", content_hash="b" * 64),
        ]
        _save_repo(tmp_path, "local", "v1", symbols)
        _save_repo(tmp_path, "local", "v2", symbols)

        result = compare_symbols("local/v1", "local/v2", storage_path=str(tmp_path))
        assert "error" not in result
        assert result["summary"]["added"] == 0
        assert result["summary"]["removed"] == 0
        assert result["summary"]["modified"] == 0
        assert result["summary"]["unchanged"] == 2

    def test_empty_base_all_added(self, tmp_path):
        """Comparing empty base to non-empty head: all symbols are added."""
        _save_repo(tmp_path, "local", "empty", [])
        symbols = [
            _make_symbol("src/mod.py::foo#function", name="foo"),
        ]
        _save_repo(tmp_path, "local", "full", symbols)

        result = compare_symbols("local/empty", "local/full", storage_path=str(tmp_path))
        assert "error" not in result
        assert result["summary"]["added"] == 1
        assert result["summary"]["removed"] == 0
        assert result["summary"]["unchanged"] == 0

    def test_empty_head_all_removed(self, tmp_path):
        """Comparing non-empty base to empty head: all symbols are removed."""
        symbols = [
            _make_symbol("src/mod.py::foo#function", name="foo"),
        ]
        _save_repo(tmp_path, "local", "full", symbols)
        _save_repo(tmp_path, "local", "empty", [])

        result = compare_symbols("local/full", "local/empty", storage_path=str(tmp_path))
        assert "error" not in result
        assert result["summary"]["added"] == 0
        assert result["summary"]["removed"] == 1
        assert result["summary"]["unchanged"] == 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unwrap(wrapped: str) -> str:
    """Extract the raw content from a wrap_untrusted_content() wrapper."""
    lines = wrapped.split("\n")
    # Format: <<<UNTRUSTED_CODE_token>>>\ncontent\n<<<END_UNTRUSTED_CODE_token>>>
    if len(lines) >= 3:
        return "\n".join(lines[1:-1])
    return wrapped
