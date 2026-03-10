"""Tests for IndexStore.incremental_save merging logic (P1-03)."""

import pytest

from codesight_mcp.storage import IndexStore
from codesight_mcp.parser import Symbol


def _make_symbol(file: str, name: str, sig: str = "", byte_offset: int = 0, byte_length: int = 10) -> Symbol:
    """Helper to build a Symbol with sensible defaults."""
    return Symbol(
        id=f"{file}::{name}#function",
        file=file,
        name=name,
        qualified_name=name,
        kind="function",
        language="python",
        signature=sig or f"def {name}():",
        summary=f"Does {name}",
        byte_offset=byte_offset,
        byte_length=byte_length,
    )


def _save_initial_index(store: IndexStore, owner: str, name: str, files_and_symbols: dict):
    """Save an initial index with the given files and their symbols.

    files_and_symbols: {file_path: (content, [Symbol, ...])}
    """
    all_symbols = []
    raw_files = {}
    source_files = []
    for fp, (content, symbols) in files_and_symbols.items():
        source_files.append(fp)
        raw_files[fp] = content
        all_symbols.extend(symbols)
    store.save_index(
        owner=owner,
        name=name,
        source_files=source_files,
        symbols=all_symbols,
        raw_files=raw_files,
        languages={"python": len(source_files)},
    )


class TestIncrementalSaveChangedFiles:
    """incremental_save with changed_files replaces only the affected file's symbols."""

    def test_changed_file_updates_symbols_preserves_others(self, tmp_path):
        """Save A, B, C. Change A only -- B and C symbols preserved, A updated."""
        store = IndexStore(base_path=str(tmp_path))
        owner, name = "test", "repo"

        sym_a = _make_symbol("a.py", "func_a")
        sym_b = _make_symbol("b.py", "func_b")
        sym_c = _make_symbol("c.py", "func_c")

        _save_initial_index(store, owner, name, {
            "a.py": ("def func_a(): pass", [sym_a]),
            "b.py": ("def func_b(): pass", [sym_b]),
            "c.py": ("def func_c(): pass", [sym_c]),
        })

        # Now change a.py -- new symbol with updated signature
        new_sym_a = _make_symbol("a.py", "func_a_v2", sig="def func_a_v2(): ...")

        updated = store.incremental_save(
            owner=owner,
            name=name,
            changed_files=["a.py"],
            new_files=[],
            deleted_files=[],
            new_symbols=[new_sym_a],
            raw_files={"a.py": "def func_a_v2(): ..."},
            languages={"python": 3},
        )

        assert updated is not None
        symbol_names = {s["name"] for s in updated.symbols}
        # Old a.py symbol removed, new one added
        assert "func_a" not in symbol_names
        assert "func_a_v2" in symbol_names
        # B and C preserved
        assert "func_b" in symbol_names
        assert "func_c" in symbol_names


class TestIncrementalSaveNewFiles:
    """incremental_save with new_files adds symbols without affecting existing ones."""

    def test_add_new_file_preserves_existing(self, tmp_path):
        """Add file D -- existing symbols for A, B, C stay, D is added."""
        store = IndexStore(base_path=str(tmp_path))
        owner, name = "test", "repo"

        sym_a = _make_symbol("a.py", "func_a")
        sym_b = _make_symbol("b.py", "func_b")

        _save_initial_index(store, owner, name, {
            "a.py": ("def func_a(): pass", [sym_a]),
            "b.py": ("def func_b(): pass", [sym_b]),
        })

        new_sym_d = _make_symbol("d.py", "func_d")

        updated = store.incremental_save(
            owner=owner,
            name=name,
            changed_files=[],
            new_files=["d.py"],
            deleted_files=[],
            new_symbols=[new_sym_d],
            raw_files={"d.py": "def func_d(): pass"},
            languages={"python": 3},
        )

        assert updated is not None
        symbol_names = {s["name"] for s in updated.symbols}
        assert "func_a" in symbol_names
        assert "func_b" in symbol_names
        assert "func_d" in symbol_names
        assert "d.py" in updated.source_files


class TestIncrementalSaveDeletedFiles:
    """incremental_save with deleted_files removes the right symbols."""

    def test_delete_file_removes_its_symbols(self, tmp_path):
        """Delete B -- B's symbols gone, A and C preserved."""
        store = IndexStore(base_path=str(tmp_path))
        owner, name = "test", "repo"

        sym_a = _make_symbol("a.py", "func_a")
        sym_b = _make_symbol("b.py", "func_b")
        sym_c = _make_symbol("c.py", "func_c")

        _save_initial_index(store, owner, name, {
            "a.py": ("def func_a(): pass", [sym_a]),
            "b.py": ("def func_b(): pass", [sym_b]),
            "c.py": ("def func_c(): pass", [sym_c]),
        })

        updated = store.incremental_save(
            owner=owner,
            name=name,
            changed_files=[],
            new_files=[],
            deleted_files=["b.py"],
            new_symbols=[],
            raw_files={},
            languages={"python": 2},
        )

        assert updated is not None
        symbol_names = {s["name"] for s in updated.symbols}
        assert "func_b" not in symbol_names
        assert "func_a" in symbol_names
        assert "func_c" in symbol_names
        assert "b.py" not in updated.source_files


class TestIncrementalSaveNoOp:
    """incremental_save with empty change lists leaves the index unchanged."""

    def test_empty_changes_preserves_index(self, tmp_path):
        """No changed/new/deleted files -- all symbols survive."""
        store = IndexStore(base_path=str(tmp_path))
        owner, name = "test", "repo"

        sym_a = _make_symbol("a.py", "func_a")
        sym_b = _make_symbol("b.py", "func_b")

        _save_initial_index(store, owner, name, {
            "a.py": ("def func_a(): pass", [sym_a]),
            "b.py": ("def func_b(): pass", [sym_b]),
        })

        updated = store.incremental_save(
            owner=owner,
            name=name,
            changed_files=[],
            new_files=[],
            deleted_files=[],
            new_symbols=[],
            raw_files={},
            languages={"python": 2},
        )

        assert updated is not None
        assert len(updated.symbols) == 2
        symbol_names = {s["name"] for s in updated.symbols}
        assert "func_a" in symbol_names
        assert "func_b" in symbol_names


class TestIncrementalSaveOverlappingSymbols:
    """incremental_save with overlapping symbol IDs -- latest wins."""

    def test_overlapping_symbol_id_latest_wins(self, tmp_path):
        """Same symbol ID in changed file gets replaced with new version."""
        store = IndexStore(base_path=str(tmp_path))
        owner, name = "test", "repo"

        original = _make_symbol("a.py", "func_a", sig="def func_a(): # v1")

        _save_initial_index(store, owner, name, {
            "a.py": ("def func_a(): # v1", [original]),
        })

        # Incremental save with a new symbol that has the SAME ID as original
        replacement = Symbol(
            id=original.id,  # same ID
            file="a.py",
            name="func_a",
            qualified_name="func_a",
            kind="function",
            language="python",
            signature="def func_a(): # v2",
            summary="Updated func_a",
            byte_offset=0,
            byte_length=20,
        )

        updated = store.incremental_save(
            owner=owner,
            name=name,
            changed_files=["a.py"],
            new_files=[],
            deleted_files=[],
            new_symbols=[replacement],
            raw_files={"a.py": "def func_a(): # v2"},
            languages={"python": 1},
        )

        assert updated is not None
        # Only one symbol with this ID
        matching = [s for s in updated.symbols if s["id"] == original.id]
        assert len(matching) == 1
        assert "v2" in matching[0]["signature"]


class TestIncrementalSaveRawFiles:
    """incremental_save updates raw_files content for changed files."""

    def test_raw_files_content_updated(self, tmp_path):
        """Changed file's raw content should be updated on disk."""
        store = IndexStore(base_path=str(tmp_path))
        owner, name = "test", "repo"

        sym_a = _make_symbol("a.py", "func_a", byte_offset=0, byte_length=18)

        _save_initial_index(store, owner, name, {
            "a.py": ("def func_a(): pass", [sym_a]),
        })

        new_content = "def func_a(): return 42"
        new_sym = _make_symbol("a.py", "func_a", sig="def func_a():", byte_offset=0, byte_length=len(new_content))

        updated = store.incremental_save(
            owner=owner,
            name=name,
            changed_files=["a.py"],
            new_files=[],
            deleted_files=[],
            new_symbols=[new_sym],
            raw_files={"a.py": new_content},
            languages={"python": 1},
        )

        assert updated is not None
        # Verify the raw content on disk by reading symbol content
        content = store.get_symbol_content(owner, name, new_sym.id, index=updated)
        assert content is not None
        assert "return 42" in content


class TestIncrementalSaveNoExistingIndex:
    """incremental_save returns None when no existing index is found."""

    def test_returns_none_without_existing_index(self, tmp_path):
        """With no prior index, incremental_save should return None."""
        store = IndexStore(base_path=str(tmp_path))

        result = store.incremental_save(
            owner="test",
            name="nonexistent",
            changed_files=[],
            new_files=["new.py"],
            deleted_files=[],
            new_symbols=[_make_symbol("new.py", "func")],
            raw_files={"new.py": "def func(): pass"},
            languages={"python": 1},
        )

        assert result is None
