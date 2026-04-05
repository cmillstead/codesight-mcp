"""Tests for batch 4 language support: css, scss, html, xml, yaml, json, toml, make.

Verifies symbol extraction, extension mapping, registry completeness,
top-level-only filtering for data formats, and name-only signatures
for config languages (no secret values leaked).
"""

import pytest

from codesight_mcp.parser.extractor import parse_file
from codesight_mcp.parser.languages import LANGUAGE_EXTENSIONS, LANGUAGE_REGISTRY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _symbol_names(symbols):
    """Extract symbol names as a set for assertion convenience."""
    return {s.name for s in symbols}


def _symbol_by_name(symbols, name):
    """Find a symbol by name."""
    for s in symbols:
        if s.name == name:
            return s
    return None


# ---------------------------------------------------------------------------
# Per-language symbol extraction tests
# ---------------------------------------------------------------------------


class TestCssSymbols:
    """CSS: rule_set and keyframes_statement extraction."""

    SOURCE = """\
.container { color: red; }
#header { margin: 0; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
"""

    def test_css_extraction(self):
        symbols = parse_file(self.SOURCE, "test.css", "css")
        names = _symbol_names(symbols)
        assert ".container" in names
        assert "#header" in names
        assert "fadeIn" in names

    def test_css_selectors(self):
        """CSS rule sets extract selector names as class kind."""
        symbols = parse_file(self.SOURCE, "test.css", "css")
        container = _symbol_by_name(symbols, ".container")
        assert container is not None
        assert container.kind == "class"

        header = _symbol_by_name(symbols, "#header")
        assert header is not None
        assert header.kind == "class"

    def test_css_keyframes(self):
        """CSS keyframes extract animation name as function kind."""
        symbols = parse_file(self.SOURCE, "test.css", "css")
        fade = _symbol_by_name(symbols, "fadeIn")
        assert fade is not None
        assert fade.kind == "function"


class TestScssSymbols:
    """SCSS: variable declarations and rule sets."""

    SOURCE = """\
$primary: blue;
$font-size: 16px;
color: red;
.btn { margin: 0; }
"""

    def test_scss_extraction(self):
        symbols = parse_file(self.SOURCE, "test.scss", "scss")
        names = _symbol_names(symbols)
        assert "$primary" in names
        assert "$font-size" in names
        assert ".btn" in names

    def test_scss_variable_only(self):
        """SCSS $variable declarations extracted, regular property declarations NOT extracted."""
        symbols = parse_file(self.SOURCE, "test.scss", "scss")
        names = _symbol_names(symbols)
        # $variables should be extracted
        assert "$primary" in names
        assert "$font-size" in names
        # Regular property like 'color: red' should NOT be extracted
        assert "color" not in names

    def test_scss_variable_kind(self):
        symbols = parse_file(self.SOURCE, "test.scss", "scss")
        primary = _symbol_by_name(symbols, "$primary")
        assert primary is not None
        assert primary.kind == "constant"


class TestHtmlSymbols:
    """HTML: root element extraction."""

    SOURCE = "<html><body><div>inner</div></body></html>"

    def test_html_extraction(self):
        symbols = parse_file(self.SOURCE, "test.html", "html")
        names = _symbol_names(symbols)
        assert "html" in names

    def test_html_root_only(self):
        """HTML root elements extracted, nested elements NOT extracted."""
        symbols = parse_file(self.SOURCE, "test.html", "html")
        names = _symbol_names(symbols)
        assert "html" in names
        # Nested elements should NOT be extracted
        assert "body" not in names
        assert "div" not in names
        assert len(symbols) == 1

    def test_html_kind(self):
        symbols = parse_file(self.SOURCE, "test.html", "html")
        html_sym = _symbol_by_name(symbols, "html")
        assert html_sym is not None
        assert html_sym.kind == "class"

    def test_html_signature_is_name(self):
        """HTML signatures should be name-only (no full element content)."""
        symbols = parse_file(self.SOURCE, "test.html", "html")
        html_sym = _symbol_by_name(symbols, "html")
        assert html_sym.signature == "html"


class TestXmlSymbols:
    """XML: root element extraction using STag/Name nodes."""

    SOURCE = "<root><child><nested/></child></root>"

    def test_xml_extraction(self):
        """XML element names extracted correctly via Name child of STag."""
        symbols = parse_file(self.SOURCE, "test.xml", "xml")
        names = _symbol_names(symbols)
        assert "root" in names

    def test_xml_root_only(self):
        """XML root elements extracted, nested elements NOT extracted."""
        symbols = parse_file(self.SOURCE, "test.xml", "xml")
        names = _symbol_names(symbols)
        assert "root" in names
        assert "child" not in names
        assert "nested" not in names
        assert len(symbols) == 1

    def test_xml_kind(self):
        symbols = parse_file(self.SOURCE, "test.xml", "xml")
        root = _symbol_by_name(symbols, "root")
        assert root is not None
        assert root.kind == "class"

    def test_xml_signature_is_name(self):
        """XML signatures should be name-only."""
        symbols = parse_file(self.SOURCE, "test.xml", "xml")
        root = _symbol_by_name(symbols, "root")
        assert root.signature == "root"


class TestYamlSymbols:
    """YAML: top-level block_mapping_pair extraction."""

    SOURCE = "key: value\nother: data"

    def test_yaml_extraction(self):
        symbols = parse_file(self.SOURCE, "test.yaml", "yaml")
        names = _symbol_names(symbols)
        assert "key" in names
        assert "other" in names

    def test_yaml_top_level_only(self):
        """YAML with nested keys only extracts top-level keys."""
        source = "top:\n  nested: value\n  deep:\n    deeper: x\nother: y"
        symbols = parse_file(source, "test.yaml", "yaml")
        names = _symbol_names(symbols)
        assert "top" in names
        assert "other" in names
        # Nested keys should NOT be extracted
        assert "nested" not in names
        assert "deep" not in names
        assert "deeper" not in names

    def test_yaml_kind(self):
        symbols = parse_file(self.SOURCE, "test.yaml", "yaml")
        key_sym = _symbol_by_name(symbols, "key")
        assert key_sym is not None
        assert key_sym.kind == "constant"

    def test_yaml_no_secret_values(self):
        """YAML with api_key: sk-secret -> signature is key name only, not value."""
        source = "api_key: sk-secret-12345\npassword: hunter2"
        symbols = parse_file(source, "test.yaml", "yaml")
        for sym in symbols:
            # Signature must be the key name only, not the full pair text
            assert "sk-secret" not in sym.signature
            assert "hunter2" not in sym.signature
            assert sym.signature == sym.name


class TestJsonSymbols:
    """JSON: top-level pair extraction."""

    SOURCE = '{"key": "value", "count": 42}'

    def test_json_extraction(self):
        symbols = parse_file(self.SOURCE, "test.json", "json")
        names = _symbol_names(symbols)
        assert "key" in names
        assert "count" in names

    def test_json_top_level_only(self):
        """JSON with nested objects only extracts top-level keys."""
        source = '{"top": {"nested": 1}, "other": 2}'
        symbols = parse_file(source, "test.json", "json")
        names = _symbol_names(symbols)
        assert "top" in names
        assert "other" in names
        assert "nested" not in names

    def test_json_root_array(self):
        """JSON root array [1,2,3] produces no symbols and no crash."""
        symbols = parse_file("[1, 2, 3]", "test.json", "json")
        assert len(symbols) == 0

    def test_json_kind(self):
        symbols = parse_file(self.SOURCE, "test.json", "json")
        key_sym = _symbol_by_name(symbols, "key")
        assert key_sym is not None
        assert key_sym.kind == "constant"

    def test_json_no_secret_values(self):
        """JSON with "password": "hunter2" -> signature is key name only."""
        source = '{"password": "hunter2", "api_key": "sk-abc123"}'
        symbols = parse_file(source, "test.json", "json")
        for sym in symbols:
            assert "hunter2" not in sym.signature
            assert "sk-abc123" not in sym.signature
            assert sym.signature == sym.name


class TestTomlSymbols:
    """TOML: table and top-level pair extraction."""

    SOURCE = 'name = "val"\nversion = "1.0"\n\n[section]\nkey = "inner"'

    def test_toml_extraction(self):
        symbols = parse_file(self.SOURCE, "test.toml", "toml")
        names = _symbol_names(symbols)
        assert "name" in names
        assert "version" in names
        assert "section" in names

    def test_toml_top_level_only(self):
        """TOML with nested tables only extracts top-level pairs and table headers."""
        source = 'top = "v"\n\n[section]\nkey = "inner"\n\n[section.sub]\ndeep = "x"'
        symbols = parse_file(source, "test.toml", "toml")
        names = _symbol_names(symbols)
        assert "top" in names
        assert "section" in names
        # Nested keys inside tables should NOT be extracted as top-level pairs
        assert "key" not in names
        assert "deep" not in names

    def test_toml_table_kind(self):
        symbols = parse_file(self.SOURCE, "test.toml", "toml")
        section = _symbol_by_name(symbols, "section")
        assert section is not None
        assert section.kind == "class"

    def test_toml_pair_kind(self):
        symbols = parse_file(self.SOURCE, "test.toml", "toml")
        name_sym = _symbol_by_name(symbols, "name")
        assert name_sym is not None
        assert name_sym.kind == "constant"

    def test_toml_no_secret_values(self):
        """TOML with api_key = "sk-secret" -> signature is key name only."""
        source = 'api_key = "sk-secret"\ndb_pass = "p@ssw0rd"'
        symbols = parse_file(source, "test.toml", "toml")
        for sym in symbols:
            assert "sk-secret" not in sym.signature
            assert "p@ssw0rd" not in sym.signature
            assert sym.signature == sym.name


class TestMakeSymbols:
    """Make: rule target extraction."""

    SOURCE = "all: main.o\n\tgcc -o all main.o\n\nclean:\n\trm -f *.o"

    def test_make_extraction(self):
        symbols = parse_file(self.SOURCE, "test.mk", "make")
        names = _symbol_names(symbols)
        assert "all" in names
        assert "clean" in names

    def test_make_targets(self):
        """Make file targets extracted as function kind."""
        symbols = parse_file(self.SOURCE, "test.mk", "make")
        all_sym = _symbol_by_name(symbols, "all")
        assert all_sym is not None
        assert all_sym.kind == "function"

        clean_sym = _symbol_by_name(symbols, "clean")
        assert clean_sym is not None
        assert clean_sym.kind == "function"

    def test_make_multi_target(self):
        """Multi-target rule extracts first target only (documented limitation)."""
        source = "all clean: main.o\n\tgcc main.o"
        symbols = parse_file(source, "test.mk", "make")
        names = _symbol_names(symbols)
        # First target should be extracted
        assert "all" in names
        # Only one symbol from this rule
        assert len(symbols) == 1


# ---------------------------------------------------------------------------
# Extension mapping tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ext,lang", [
    (".css", "css"),
    (".scss", "scss"),
    (".html", "html"),
    (".htm", "html"),
    (".xml", "xml"),
    (".xsl", "xml"),
    (".xsd", "xml"),
    (".yaml", "yaml"),
    (".yml", "yaml"),
    (".json", "json"),
    (".toml", "toml"),
    (".mk", "make"),
])
def test_extension_mapping(ext, lang):
    """Verify all batch 4 file extensions map to the correct language."""
    assert LANGUAGE_EXTENSIONS[ext] == lang


# ---------------------------------------------------------------------------
# Registry completeness test
# ---------------------------------------------------------------------------

BATCH4_LANGUAGES = ["css", "scss", "html", "xml", "yaml", "json", "toml", "make"]


def test_batch4_in_registry():
    """All 8 batch 4 languages must be registered in LANGUAGE_REGISTRY."""
    for lang in BATCH4_LANGUAGES:
        assert lang in LANGUAGE_REGISTRY, f"{lang} not in LANGUAGE_REGISTRY"


# ---------------------------------------------------------------------------
# Edge case tests (Codex R3 fixes)
# ---------------------------------------------------------------------------


class TestXmlSelfClosing:
    """XML: self-closing root elements use EmptyElemTag, not STag."""

    def test_xml_self_closing_root(self):
        """Self-closing XML root like <root/> should be extracted."""
        symbols = parse_file("<root/>", "test.xml", "xml")
        names = _symbol_names(symbols)
        assert "root" in names
        assert len(symbols) == 1

    def test_xml_self_closing_with_prolog(self):
        """XML with prolog + self-closing root."""
        symbols = parse_file('<?xml version="1.0"?><root/>', "test.xml", "xml")
        names = _symbol_names(symbols)
        assert "root" in names


class TestTomlQuotedKeys:
    """TOML: quoted keys should be extracted with quotes stripped."""

    def test_toml_quoted_key(self):
        """Quoted TOML key like "database-url" should be extracted."""
        source = '"database-url" = "postgres://localhost"'
        symbols = parse_file(source, "test.toml", "toml")
        names = _symbol_names(symbols)
        assert "database-url" in names

    def test_toml_quoted_key_no_secret(self):
        """Quoted TOML key signature should be name-only."""
        source = '"api-key" = "sk-secret-12345"'
        symbols = parse_file(source, "test.toml", "toml")
        for sym in symbols:
            assert "sk-secret" not in sym.signature
            assert sym.signature == sym.name


class TestYamlQuotedKeys:
    """YAML: quoted keys should be extracted with quotes stripped."""

    def test_yaml_quoted_key(self):
        """Quoted YAML key like "key-name" should be extracted without quotes."""
        source = '"key-name": value\nother: 1'
        symbols = parse_file(source, "test.yaml", "yaml")
        names = _symbol_names(symbols)
        assert "key-name" in names
        assert '"key-name"' not in names  # quotes must be stripped
