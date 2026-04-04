"""Tests for get_symbol file:line lookup (Task 14)."""

import hashlib


from codesight_mcp.tools.get_symbol import get_symbol, _find_symbol_at_line
from codesight_mcp.storage import IndexStore
from codesight_mcp.parser import Symbol


def _make_indexed_repo(tmp_path):
    """Create an index with overlapping symbols for file:line testing.

    Layout:
        class MyClass:           # lines 1-8
            def method_a(self):  # lines 2-4
                pass
            def method_b(self):  # lines 5-8
                x = 1
                y = 2
                return x + y
        def standalone():        # lines 9-10
            pass
    """
    class_src = (
        "class MyClass:\n"
        "    def method_a(self):\n"
        "        pass\n"
        "        pass\n"
        "    def method_b(self):\n"
        "        x = 1\n"
        "        y = 2\n"
        "        return x + y\n"
    )
    standalone_src = "def standalone():\n    pass\n"
    full_content = class_src + standalone_src

    class_hash = hashlib.sha256(class_src.encode("utf-8")).hexdigest()
    method_a_src = "    def method_a(self):\n        pass\n        pass\n"
    method_a_hash = hashlib.sha256(method_a_src.encode("utf-8")).hexdigest()
    method_b_src = "    def method_b(self):\n        x = 1\n        y = 2\n        return x + y\n"
    method_b_hash = hashlib.sha256(method_b_src.encode("utf-8")).hexdigest()
    standalone_hash = hashlib.sha256(standalone_src.encode("utf-8")).hexdigest()

    symbols = [
        Symbol(
            id="app.py::MyClass#class",
            file="app.py",
            name="MyClass",
            qualified_name="MyClass",
            kind="class",
            language="python",
            signature="class MyClass:",
            summary="A class",
            line=1, end_line=8,
            byte_offset=0, byte_length=len(class_src),
            content_hash=class_hash,
        ),
        Symbol(
            id="app.py::MyClass.method_a#method",
            file="app.py",
            name="method_a",
            qualified_name="MyClass.method_a",
            kind="method",
            language="python",
            signature="def method_a(self):",
            summary="Method A",
            parent="app.py::MyClass#class",
            line=2, end_line=4,
            byte_offset=len("class MyClass:\n"),
            byte_length=len(method_a_src),
            content_hash=method_a_hash,
        ),
        Symbol(
            id="app.py::MyClass.method_b#method",
            file="app.py",
            name="method_b",
            qualified_name="MyClass.method_b",
            kind="method",
            language="python",
            signature="def method_b(self):",
            summary="Method B",
            parent="app.py::MyClass#class",
            line=5, end_line=8,
            byte_offset=len("class MyClass:\n") + len(method_a_src),
            byte_length=len(method_b_src),
            content_hash=method_b_hash,
        ),
        Symbol(
            id="app.py::standalone#function",
            file="app.py",
            name="standalone",
            qualified_name="standalone",
            kind="function",
            language="python",
            signature="def standalone():",
            summary="A standalone function",
            line=9, end_line=10,
            byte_offset=len(class_src),
            byte_length=len(standalone_src),
            content_hash=standalone_hash,
        ),
    ]

    store = IndexStore(base_path=str(tmp_path))
    content_dir = tmp_path / "local__testapp"
    content_dir.mkdir(parents=True, exist_ok=True)
    (content_dir / "app.py").write_text(full_content)

    store.save_index(
        owner="local",
        name="testapp",
        source_files=["app.py"],
        symbols=symbols,
        raw_files={"app.py": full_content},
        languages={"python": 1},
    )
    return store, symbols


# ---------------------------------------------------------------------------
# _find_symbol_at_line helper
# ---------------------------------------------------------------------------


class TestFindSymbolAtLine:
    """Tests for the _find_symbol_at_line helper."""

    def test_finds_innermost_symbol(self, tmp_path):
        """When line is inside a method that's inside a class, return the method."""
        store, _ = _make_indexed_repo(tmp_path)
        index = store.load_index("local", "testapp")

        result = _find_symbol_at_line(index, "app.py", 3)
        assert result is not None
        assert result["id"] == "app.py::MyClass.method_a#method"

    def test_finds_class_on_class_line(self, tmp_path):
        """Line 1 is the class definition itself -- method_a starts at 2."""
        store, _ = _make_indexed_repo(tmp_path)
        index = store.load_index("local", "testapp")

        # Line 1 only contains the class, not any method
        result = _find_symbol_at_line(index, "app.py", 1)
        assert result is not None
        # The class spans 1-8 and is the only symbol starting at line 1
        assert result["id"] == "app.py::MyClass#class"

    def test_finds_standalone_function(self, tmp_path):
        """Line 9 should find the standalone function."""
        store, _ = _make_indexed_repo(tmp_path)
        index = store.load_index("local", "testapp")

        result = _find_symbol_at_line(index, "app.py", 9)
        assert result is not None
        assert result["id"] == "app.py::standalone#function"

    def test_returns_none_for_nonexistent_line(self, tmp_path):
        """A line beyond all symbols should return None."""
        store, _ = _make_indexed_repo(tmp_path)
        index = store.load_index("local", "testapp")

        result = _find_symbol_at_line(index, "app.py", 100)
        assert result is None

    def test_returns_none_for_wrong_file(self, tmp_path):
        """A non-existent file should return None."""
        store, _ = _make_indexed_repo(tmp_path)
        index = store.load_index("local", "testapp")

        result = _find_symbol_at_line(index, "nonexistent.py", 1)
        assert result is None


# ---------------------------------------------------------------------------
# get_symbol with file_path + line
# ---------------------------------------------------------------------------


class TestGetSymbolFileLine:
    """Tests for get_symbol using file_path and line parameters."""

    def test_lookup_by_file_line(self, tmp_path):
        """Should return the symbol at the given file:line."""
        _make_indexed_repo(tmp_path)
        result = get_symbol(
            repo="local/testapp",
            file_path="app.py",
            line=6,
            storage_path=str(tmp_path),
        )

        assert "error" not in result
        assert "method_b" in result["name"]
        assert result["kind"] == "method"

    def test_lookup_standalone_function(self, tmp_path):
        """file:line lookup for standalone function."""
        _make_indexed_repo(tmp_path)
        result = get_symbol(
            repo="local/testapp",
            file_path="app.py",
            line=9,
            storage_path=str(tmp_path),
        )

        assert "error" not in result
        assert "standalone" in result["name"]

    def test_file_line_no_symbol_returns_error(self, tmp_path):
        """Should return error when no symbol at the given line."""
        _make_indexed_repo(tmp_path)
        result = get_symbol(
            repo="local/testapp",
            file_path="app.py",
            line=100,
            storage_path=str(tmp_path),
        )

        assert "error" in result
        assert "app.py:100" in result["error"]

    def test_symbol_id_takes_precedence(self, tmp_path):
        """When both symbol_id and file:line are provided, symbol_id wins."""
        _make_indexed_repo(tmp_path)
        result = get_symbol(
            repo="local/testapp",
            symbol_id="app.py::standalone#function",
            file_path="app.py",
            line=3,
            storage_path=str(tmp_path),
        )

        assert "error" not in result
        assert "standalone" in result["name"]

    def test_neither_symbol_id_nor_file_line_returns_error(self, tmp_path):
        """Should return error when neither symbol_id nor file:line is provided."""
        _make_indexed_repo(tmp_path)
        result = get_symbol(
            repo="local/testapp",
            storage_path=str(tmp_path),
        )

        assert "error" in result
        assert "required" in result["error"].lower()

    def test_file_path_without_line_returns_error(self, tmp_path):
        """file_path alone (without line) should return error."""
        _make_indexed_repo(tmp_path)
        result = get_symbol(
            repo="local/testapp",
            file_path="app.py",
            storage_path=str(tmp_path),
        )

        assert "error" in result

    def test_file_line_with_context(self, tmp_path):
        """file:line lookup should work with context_lines."""
        _make_indexed_repo(tmp_path)
        result = get_symbol(
            repo="local/testapp",
            file_path="app.py",
            line=9,
            context_lines=2,
            storage_path=str(tmp_path),
        )

        assert "error" not in result
        assert "standalone" in result["name"]
        # standalone is at lines 9-10, so there should be context_before
        assert "context_before" in result

    def test_file_line_with_verify(self, tmp_path):
        """file:line lookup should work with verify=True."""
        _make_indexed_repo(tmp_path)
        result = get_symbol(
            repo="local/testapp",
            file_path="app.py",
            line=9,
            verify=True,
            storage_path=str(tmp_path),
        )

        assert "error" not in result
        assert "_meta" in result
        assert "content_verified" in result["_meta"]
