"""Tests for the get_context tool."""

import pytest

from codesight_mcp.tools.get_context import get_context
from codesight_mcp.storage import IndexStore
from codesight_mcp.parser import Symbol


# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------

def _make_class_repo(tmp_path):
    """Index a repo with a class (two methods) and a module-level function.

    Layout:
      calc.py:
        class Calculator:          (line 1-8)
          def add(self, a, b):     (line 2-3) -- parent: Calculator
          def subtract(self, a, b): (line 4-5) -- parent: Calculator
        def standalone():          (line 7-8)

      other.py:
        def unrelated():           (line 1-2)
    """
    calc_src = (
        "class Calculator:\n"
        "    def add(self, a, b):\n"
        "        return a + b\n"
        "    def subtract(self, a, b):\n"
        "        return a - b\n"
        "\n"
        "def standalone():\n"
        "    pass\n"
    )
    other_src = (
        "def unrelated():\n"
        "    pass\n"
    )

    class_sym = Symbol(
        id="calc.py::Calculator#class",
        file="calc.py",
        name="Calculator",
        qualified_name="Calculator",
        kind="class",
        language="python",
        signature="class Calculator:",
        summary="A calculator class",
        line=1, end_line=5,
        byte_offset=0, byte_length=90,
    )
    add_sym = Symbol(
        id="calc.py::Calculator.add#method",
        file="calc.py",
        name="add",
        qualified_name="Calculator.add",
        kind="method",
        language="python",
        signature="def add(self, a, b):",
        summary="Add two numbers",
        parent="calc.py::Calculator#class",
        line=2, end_line=3,
        byte_offset=20, byte_length=34,
    )
    subtract_sym = Symbol(
        id="calc.py::Calculator.subtract#method",
        file="calc.py",
        name="subtract",
        qualified_name="Calculator.subtract",
        kind="method",
        language="python",
        signature="def subtract(self, a, b):",
        summary="Subtract two numbers",
        parent="calc.py::Calculator#class",
        line=4, end_line=5,
        byte_offset=54, byte_length=40,
    )
    standalone_sym = Symbol(
        id="calc.py::standalone#function",
        file="calc.py",
        name="standalone",
        qualified_name="standalone",
        kind="function",
        language="python",
        signature="def standalone():",
        summary="A standalone function",
        line=7, end_line=8,
        byte_offset=95, byte_length=20,
    )
    unrelated_sym = Symbol(
        id="other.py::unrelated#function",
        file="other.py",
        name="unrelated",
        qualified_name="unrelated",
        kind="function",
        language="python",
        signature="def unrelated():",
        summary="An unrelated function",
        line=1, end_line=2,
        byte_offset=0, byte_length=20,
    )

    store = IndexStore(base_path=str(tmp_path))
    store.save_index(
        owner="local",
        name="myproject",
        source_files=["calc.py", "other.py"],
        symbols=[class_sym, add_sym, subtract_sym, standalone_sym, unrelated_sym],
        raw_files={"calc.py": calc_src, "other.py": other_src},
        languages={"python": 2},
    )
    return store


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestGetContextMethodSiblings:
    """Method targets should get class siblings, not symbols from other files."""

    def test_method_returns_sibling_method(self, tmp_path):
        """get_context on a method should include the other method as a sibling."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::Calculator.add#method",
            storage_path=str(tmp_path),
        )

        assert "error" not in result
        sibling_ids = [s["id"] for s in result["siblings"]]
        # subtract should appear as a sibling (unwrap marker prefix to check name)
        assert any("subtract" in sid for sid in sibling_ids)

    def test_method_excludes_target_from_siblings(self, tmp_path):
        """The target symbol must not appear in its own siblings list."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::Calculator.add#method",
            storage_path=str(tmp_path),
        )

        sibling_ids = [s["id"] for s in result["siblings"]]
        assert not any("Calculator.add#method" in sid for sid in sibling_ids)

    def test_method_excludes_symbols_from_other_files(self, tmp_path):
        """Symbols in other files must never appear as siblings."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::Calculator.add#method",
            storage_path=str(tmp_path),
        )

        sibling_ids = [s["id"] for s in result["siblings"]]
        assert not any("other.py" in sid for sid in sibling_ids)

    def test_method_sibling_count_is_correct(self, tmp_path):
        """Two-method class: each method should see exactly one sibling."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::Calculator.add#method",
            storage_path=str(tmp_path),
        )

        assert result["_meta"]["sibling_count"] == 1
        assert len(result["siblings"]) == 1

    def test_method_excludes_standalone_function_as_sibling(self, tmp_path):
        """Module-level functions must not appear as siblings of a method."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::Calculator.add#method",
            storage_path=str(tmp_path),
        )

        sibling_ids = [s["id"] for s in result["siblings"]]
        assert not any("standalone" in sid for sid in sibling_ids)


class TestGetContextParent:
    """Parent symbol should be returned for methods; None for module-level."""

    def test_method_has_class_as_parent(self, tmp_path):
        """A method should report its containing class as parent."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::Calculator.add#method",
            storage_path=str(tmp_path),
        )

        assert result["parent"] is not None
        assert "Calculator" in result["parent"]["name"]
        assert result["parent"]["kind"] == "class"

    def test_module_level_function_has_no_parent(self, tmp_path):
        """A top-level function should have parent=None."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::standalone#function",
            storage_path=str(tmp_path),
        )

        assert result["parent"] is None


class TestGetContextModuleLevelSiblings:
    """Module-level functions should list other module-level symbols as siblings."""

    def test_module_level_function_sees_class_as_sibling(self, tmp_path):
        """standalone() should see Calculator class as a sibling (both module-level)."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::standalone#function",
            storage_path=str(tmp_path),
        )

        sibling_ids = [s["id"] for s in result["siblings"]]
        assert any("Calculator#class" in sid for sid in sibling_ids)

    def test_module_level_function_excludes_methods_as_siblings(self, tmp_path):
        """standalone() must not see methods (which have a parent) as siblings."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::standalone#function",
            storage_path=str(tmp_path),
        )

        sibling_ids = [s["id"] for s in result["siblings"]]
        assert not any("Calculator.add" in sid for sid in sibling_ids)
        assert not any("Calculator.subtract" in sid for sid in sibling_ids)

    def test_module_level_function_excludes_other_files(self, tmp_path):
        """Module-level siblings from other files must not appear."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::standalone#function",
            storage_path=str(tmp_path),
        )

        sibling_ids = [s["id"] for s in result["siblings"]]
        assert not any("other.py" in sid for sid in sibling_ids)


class TestGetContextSymbolData:
    """Target symbol should have source and correct fields."""

    def test_symbol_has_source(self, tmp_path):
        """The symbol dict in result should include non-empty source."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::Calculator.add#method",
            storage_path=str(tmp_path),
        )

        assert "source" in result["symbol"]
        assert result["symbol"]["source"] != ""

    def test_symbol_source_is_wrapped(self, tmp_path):
        """Source should be wrapped with untrusted content markers."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::Calculator.add#method",
            storage_path=str(tmp_path),
        )

        assert result["symbol"]["source"].startswith("<<<UNTRUSTED_CODE_")

    def test_symbol_has_required_fields(self, tmp_path):
        """Symbol dict should include id, kind, name, signature, line, end_line, summary."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::Calculator.add#method",
            storage_path=str(tmp_path),
        )

        sym = result["symbol"]
        for field in ("id", "kind", "name", "signature", "line", "end_line", "summary", "source"):
            assert field in sym, f"Missing field: {field}"

    def test_siblings_have_no_source_field(self, tmp_path):
        """Sibling dicts should include signatures but NOT source code."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::Calculator.add#method",
            storage_path=str(tmp_path),
        )

        for sibling in result["siblings"]:
            assert "source" not in sibling

    def test_siblings_sorted_by_line(self, tmp_path):
        """Siblings should be returned in line-number order."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::Calculator.add#method",
            storage_path=str(tmp_path),
        )

        lines = [s["line"] for s in result["siblings"]]
        assert lines == sorted(lines)


class TestGetContextMeta:
    """_meta envelope should include required fields."""

    def test_meta_has_timing_ms(self, tmp_path):
        """Result _meta should include timing_ms."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::Calculator.add#method",
            storage_path=str(tmp_path),
        )

        assert "_meta" in result
        assert "timing_ms" in result["_meta"]

    def test_meta_has_sibling_count(self, tmp_path):
        """Result _meta should include sibling_count matching siblings list length."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::Calculator.add#method",
            storage_path=str(tmp_path),
        )

        assert result["_meta"]["sibling_count"] == len(result["siblings"])

    def test_meta_content_trust_is_untrusted(self, tmp_path):
        """contentTrust should be 'untrusted' since we return source code."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::Calculator.add#method",
            storage_path=str(tmp_path),
        )

        assert result["_meta"]["contentTrust"] == "untrusted"


# ---------------------------------------------------------------------------
# Error-handling tests
# ---------------------------------------------------------------------------

class TestGetContextErrors:
    """Error cases should return error dicts, never raise exceptions."""

    def test_unknown_symbol_returns_error(self, tmp_path):
        """A non-existent symbol ID should return an error dict."""
        _make_class_repo(tmp_path)
        result = get_context(
            repo="local/myproject",
            symbol_id="calc.py::DoesNotExist#function",
            storage_path=str(tmp_path),
        )

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_unknown_repo_returns_error(self, tmp_path):
        """A non-existent repo should return an error dict."""
        result = get_context(
            repo="nobody/norepo",
            symbol_id="any::sym#function",
            storage_path=str(tmp_path),
        )

        assert "error" in result

    def test_unindexed_repo_returns_error(self, tmp_path):
        """A valid-looking but unindexed repo should return an error."""
        result = get_context(
            repo="owner/missing",
            symbol_id="foo.py::bar#function",
            storage_path=str(tmp_path),
        )

        assert "error" in result
