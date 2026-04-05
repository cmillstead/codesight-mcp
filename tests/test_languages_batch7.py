"""Tests for batch 7 language support: glsl, hlsl, wgsl, nix.

Verifies symbol extraction, extension mapping, and registry completeness
for shader languages and the Nix configuration language.
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
# GLSL tests
# ---------------------------------------------------------------------------


class TestGlslSymbols:
    """GLSL: function and struct extraction."""

    def test_glsl_function(self, tmp_path):
        source = """\
void main() {
    gl_Position = vec4(0.0);
}
"""
        symbols = parse_file(source, str(tmp_path / "test.glsl"), "glsl")
        names = _symbol_names(symbols)
        assert "main" in names
        main_sym = _symbol_by_name(symbols, "main")
        assert main_sym.kind == "function"

    def test_glsl_struct(self, tmp_path):
        source = """\
struct Light {
    vec3 position;
    vec3 color;
    float intensity;
};
"""
        symbols = parse_file(source, str(tmp_path / "test.glsl"), "glsl")
        names = _symbol_names(symbols)
        assert "Light" in names
        light = _symbol_by_name(symbols, "Light")
        assert light.kind == "type"


# ---------------------------------------------------------------------------
# HLSL tests
# ---------------------------------------------------------------------------


class TestHlslSymbols:
    """HLSL: function extraction."""

    def test_hlsl_function(self, tmp_path):
        source = """\
float4 main() : SV_Target {
    return float4(1, 1, 1, 1);
}
"""
        symbols = parse_file(source, str(tmp_path / "test.hlsl"), "hlsl")
        names = _symbol_names(symbols)
        assert "main" in names
        main_sym = _symbol_by_name(symbols, "main")
        assert main_sym.kind == "function"


# ---------------------------------------------------------------------------
# WGSL tests
# ---------------------------------------------------------------------------


class TestWgslSymbols:
    """WGSL: function and struct extraction."""

    def test_wgsl_function(self, tmp_path):
        source = """\
fn vs_main() -> vec4f {
    return vec4f(0.0);
}
"""
        symbols = parse_file(source, str(tmp_path / "test.wgsl"), "wgsl")
        names = _symbol_names(symbols)
        assert "vs_main" in names
        vs = _symbol_by_name(symbols, "vs_main")
        assert vs.kind == "function"

    def test_wgsl_struct(self, tmp_path):
        source = """\
struct VertexOutput {
    position: vec4f,
    color: vec4f,
}
"""
        symbols = parse_file(source, str(tmp_path / "test.wgsl"), "wgsl")
        names = _symbol_names(symbols)
        assert "VertexOutput" in names
        vo = _symbol_by_name(symbols, "VertexOutput")
        assert vo.kind == "class"


# ---------------------------------------------------------------------------
# Nix tests
# ---------------------------------------------------------------------------


class TestNixSymbols:
    """Nix: let-binding extraction."""

    def test_nix_binding(self, tmp_path):
        source = """\
let
  hello = 42;
in hello
"""
        symbols = parse_file(source, str(tmp_path / "test.nix"), "nix")
        names = _symbol_names(symbols)
        assert "hello" in names
        hello = _symbol_by_name(symbols, "hello")
        assert hello.kind == "constant"

    def test_nix_signature_name_only(self, tmp_path):
        """Nix signatures should be name-only (no values, to avoid leaking secrets)."""
        source = """\
let
  secret = "supersecretvalue";
in secret
"""
        symbols = parse_file(source, str(tmp_path / "test.nix"), "nix")
        secret = _symbol_by_name(symbols, "secret")
        assert secret is not None
        assert secret.signature == "secret"
        assert "supersecretvalue" not in secret.signature


# ---------------------------------------------------------------------------
# Extension mapping tests
# ---------------------------------------------------------------------------


BATCH7_EXTENSIONS = [
    (".glsl", "glsl"),
    (".vert", "glsl"),
    (".frag", "glsl"),
    (".geom", "glsl"),
    (".comp", "glsl"),
    (".hlsl", "hlsl"),
    (".fx", "hlsl"),
    (".wgsl", "wgsl"),
    (".nix", "nix"),
]


class TestBatch7Extensions:
    """Verify extension -> language mapping for batch 7 languages."""

    @pytest.mark.parametrize(
        "ext,expected_lang",
        BATCH7_EXTENSIONS,
        ids=[e[0] for e in BATCH7_EXTENSIONS],
    )
    def test_extension_mapping(self, ext, expected_lang):
        assert LANGUAGE_EXTENSIONS[ext] == expected_lang


class TestBatch7Registry:
    """Verify all batch 7 languages are in the registry."""

    BATCH7_LANGUAGES = ["glsl", "hlsl", "wgsl", "nix"]

    @pytest.mark.parametrize("lang", BATCH7_LANGUAGES)
    def test_language_in_registry(self, lang):
        assert lang in LANGUAGE_REGISTRY, f"{lang} not in LANGUAGE_REGISTRY"

    def test_registry_count(self):
        """Registry should have at least 66 languages (62 existing + 4 new)."""
        assert len(LANGUAGE_REGISTRY) >= 66
