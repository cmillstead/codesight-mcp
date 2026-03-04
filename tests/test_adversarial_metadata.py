"""Tests for untrusted metadata handling — prompt injection prevention."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from ironmunch.storage.index_store import IndexStore
from ironmunch.parser.symbols import Symbol
from ironmunch.tools.search_symbols import search_symbols
from ironmunch.tools.get_file_outline import get_file_outline


def _create_index_with_symbol(tmp):
    """Create an index with a symbol for testing."""
    symbols = [Symbol(
        id="src/test.py::hello#function",
        file="src/test.py",
        name="hello",
        qualified_name="hello",
        kind="function",
        language="python",
        signature="def hello():",
        docstring="Say hello.",
        summary="Says hello",
        decorators=[],
        keywords=[],
        parent=None,
        line=1, end_line=3,
        byte_offset=0, byte_length=30,
        content_hash="a" * 64,
    )]

    store = IndexStore(tmp)
    content_dir = Path(tmp) / "test__repo"
    content_dir.mkdir(parents=True, exist_ok=True)
    src_dir = content_dir / "src"
    src_dir.mkdir()
    (src_dir / "test.py").write_text("def hello():\n    pass\n")

    store.save_index(
        owner="test", name="repo",
        source_files=["src/test.py"],
        symbols=symbols,
        raw_files={"src/test.py": "def hello():\n    pass\n"},
        languages={"python": 1},
    )
    return store


class TestSearchSymbolsTrustMarking:
    """search_symbols must mark content as untrusted."""

    def test_meta_marks_untrusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            _create_index_with_symbol(tmp)
            result = search_symbols(
                repo="test/repo", query="hello", storage_path=tmp
            )
            meta = result.get("_meta", {})
            assert meta.get("contentTrust") == "untrusted", \
                "search_symbols returns code-derived data — must be marked untrusted"

    def test_meta_has_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            _create_index_with_symbol(tmp)
            result = search_symbols(
                repo="test/repo", query="hello", storage_path=tmp
            )
            meta = result.get("_meta", {})
            assert "warning" in meta, "untrusted meta must include warning"


class TestFileOutlineTrustMarking:
    """get_file_outline must mark content as untrusted."""

    def test_meta_marks_untrusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            _create_index_with_symbol(tmp)
            result = get_file_outline(
                repo="test/repo", file_path="src/test.py", storage_path=tmp
            )
            meta = result.get("_meta", {})
            assert meta.get("contentTrust") == "untrusted", \
                "get_file_outline returns code-derived data — must be marked untrusted"

    def test_meta_has_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            _create_index_with_symbol(tmp)
            result = get_file_outline(
                repo="test/repo", file_path="src/test.py", storage_path=tmp
            )
            meta = result.get("_meta", {})
            assert "warning" in meta, "untrusted meta must include warning"
