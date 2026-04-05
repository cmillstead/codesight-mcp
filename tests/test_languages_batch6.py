"""Tests for batch 6 language support: ada, pascal, commonlisp, scheme, racket, tcl, dockerfile.

Verifies symbol extraction, extension mapping, and registry completeness
for classic, Lisp-family, scripting, and DevOps languages.
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
# Ada tests
# ---------------------------------------------------------------------------


class TestAdaSymbols:
    """Ada: procedure and function extraction from subprogram_body."""

    def test_ada_procedure(self, tmp_path):
        source = """\
procedure Hello is
begin
  null;
end Hello;
"""
        symbols = parse_file(source, str(tmp_path / "test.adb"), "ada")
        names = _symbol_names(symbols)
        assert "Hello" in names
        hello = _symbol_by_name(symbols, "Hello")
        assert hello.kind == "function"

    def test_ada_function(self, tmp_path):
        source = """\
function Add(X : Integer; Y : Integer) return Integer is
begin
  return X + Y;
end Add;
"""
        symbols = parse_file(source, str(tmp_path / "test.adb"), "ada")
        names = _symbol_names(symbols)
        assert "Add" in names
        add_sym = _symbol_by_name(symbols, "Add")
        assert add_sym.kind == "function"


# ---------------------------------------------------------------------------
# Pascal tests
# ---------------------------------------------------------------------------


class TestPascalSymbols:
    """Pascal: program, procedure, and function extraction."""

    def test_pascal_program(self, tmp_path):
        source = """\
program Hello;
begin
end.
"""
        symbols = parse_file(source, str(tmp_path / "test.pas"), "pascal")
        names = _symbol_names(symbols)
        assert "Hello" in names
        hello = _symbol_by_name(symbols, "Hello")
        assert hello.kind == "class"

    def test_pascal_procedure(self, tmp_path):
        source = """\
program Main;
procedure Greet;
begin
  writeln('Hello');
end;
begin
end.
"""
        symbols = parse_file(source, str(tmp_path / "test.pas"), "pascal")
        names = _symbol_names(symbols)
        assert "Greet" in names
        greet = _symbol_by_name(symbols, "Greet")
        assert greet.kind in ("function", "method")

    def test_pascal_function(self, tmp_path):
        source = """\
program Main;
function Add(a, b: Integer): Integer;
begin
  Add := a + b;
end;
begin
end.
"""
        symbols = parse_file(source, str(tmp_path / "test.pas"), "pascal")
        names = _symbol_names(symbols)
        assert "Add" in names
        add_sym = _symbol_by_name(symbols, "Add")
        assert add_sym.kind in ("function", "method")


# ---------------------------------------------------------------------------
# Common Lisp tests
# ---------------------------------------------------------------------------


class TestCommonLispSymbols:
    """Common Lisp: defun extraction."""

    def test_commonlisp_defun(self, tmp_path):
        source = "(defun hello (x) (+ x 1))"
        symbols = parse_file(source, str(tmp_path / "test.lisp"), "commonlisp")
        names = _symbol_names(symbols)
        assert "hello" in names
        hello = _symbol_by_name(symbols, "hello")
        assert hello.kind == "function"


# ---------------------------------------------------------------------------
# Scheme tests
# ---------------------------------------------------------------------------


class TestSchemeSymbols:
    """Scheme: define form extraction for functions, constants, and nested defines."""

    def test_scheme_define_function(self, tmp_path):
        source = "(define (hello x) (+ x 1))"
        symbols = parse_file(source, str(tmp_path / "test.scm"), "scheme")
        names = _symbol_names(symbols)
        assert "hello" in names
        hello = _symbol_by_name(symbols, "hello")
        assert hello.kind == "function"

    def test_scheme_define_constant(self, tmp_path):
        source = "(define pi 3.14159)"
        symbols = parse_file(source, str(tmp_path / "test.scm"), "scheme")
        names = _symbol_names(symbols)
        assert "pi" in names
        pi_sym = _symbol_by_name(symbols, "pi")
        assert pi_sym.kind == "constant"

    def test_scheme_non_define_skipped(self, tmp_path):
        source = "(+ 1 2)"
        symbols = parse_file(source, str(tmp_path / "test.scm"), "scheme")
        assert len(symbols) == 0

    def test_scheme_nested_define(self, tmp_path):
        source = """\
(define (outer x)
  (define (inner y) (+ x y))
  (inner x))
"""
        symbols = parse_file(source, str(tmp_path / "test.scm"), "scheme")
        names = _symbol_names(symbols)
        assert "outer" in names
        assert "inner" in names
        inner = _symbol_by_name(symbols, "inner")
        assert inner.kind == "method"


# ---------------------------------------------------------------------------
# Racket tests
# ---------------------------------------------------------------------------


class TestRacketSymbols:
    """Racket: define form extraction (shares Scheme logic)."""

    def test_racket_define_function(self, tmp_path):
        source = """\
#lang racket
(define (hello x) (+ x 1))
"""
        symbols = parse_file(source, str(tmp_path / "test.rkt"), "racket")
        names = _symbol_names(symbols)
        assert "hello" in names
        hello = _symbol_by_name(symbols, "hello")
        assert hello.kind == "function"

    def test_racket_define_constant(self, tmp_path):
        source = """\
#lang racket
(define pi 3.14159)
"""
        symbols = parse_file(source, str(tmp_path / "test.rkt"), "racket")
        names = _symbol_names(symbols)
        assert "pi" in names
        pi_sym = _symbol_by_name(symbols, "pi")
        assert pi_sym.kind == "constant"


# ---------------------------------------------------------------------------
# Tcl tests
# ---------------------------------------------------------------------------


class TestTclSymbols:
    """Tcl: procedure extraction."""

    def test_tcl_proc(self, tmp_path):
        source = "proc hello {name} { puts $name }"
        symbols = parse_file(source, str(tmp_path / "test.tcl"), "tcl")
        names = _symbol_names(symbols)
        assert "hello" in names
        hello = _symbol_by_name(symbols, "hello")
        assert hello.kind == "function"


# ---------------------------------------------------------------------------
# Dockerfile tests
# ---------------------------------------------------------------------------


class TestDockerfileSymbols:
    """Dockerfile: FROM instruction extraction."""

    def test_dockerfile_from(self, tmp_path):
        source = "FROM ubuntu:22.04"
        symbols = parse_file(source, str(tmp_path / "test.dockerfile"), "dockerfile")
        names = _symbol_names(symbols)
        assert "ubuntu" in names
        ubuntu = _symbol_by_name(symbols, "ubuntu")
        assert ubuntu.kind == "class"

    def test_dockerfile_signature_name_only(self, tmp_path):
        source = "FROM python:3.12-slim"
        symbols = parse_file(source, str(tmp_path / "test.dockerfile"), "dockerfile")
        python_sym = _symbol_by_name(symbols, "python")
        assert python_sym is not None
        # signature_from_name=True means signature is just the name, no tags
        assert python_sym.signature == "python"

    def test_dockerfile_digest(self, tmp_path):
        source = "FROM node@sha256:abc123def456"
        symbols = parse_file(source, str(tmp_path / "test.dockerfile"), "dockerfile")
        names = _symbol_names(symbols)
        assert "node" in names
        node_sym = _symbol_by_name(symbols, "node")
        assert node_sym.kind == "class"
        assert node_sym.signature == "node"


# ---------------------------------------------------------------------------
# Extension mapping tests
# ---------------------------------------------------------------------------


BATCH6_EXTENSIONS = [
    (".adb", "ada"),
    (".ads", "ada"),
    (".pas", "pascal"),
    (".pp", "pascal"),
    (".lisp", "commonlisp"),
    (".cl", "commonlisp"),
    (".lsp", "commonlisp"),
    (".scm", "scheme"),
    (".ss", "scheme"),
    (".rkt", "racket"),
    (".tcl", "tcl"),
    (".dockerfile", "dockerfile"),
]


class TestBatch6Extensions:
    """Verify extension -> language mapping for batch 6 languages."""

    @pytest.mark.parametrize(
        "ext,expected_lang",
        BATCH6_EXTENSIONS,
        ids=[e[0] for e in BATCH6_EXTENSIONS],
    )
    def test_extension_mapping(self, ext, expected_lang):
        assert LANGUAGE_EXTENSIONS[ext] == expected_lang


class TestBatch6Registry:
    """Verify all batch 6 languages are in the registry."""

    BATCH6_LANGUAGES = [
        "ada", "pascal", "commonlisp", "scheme", "racket", "tcl", "dockerfile",
    ]

    @pytest.mark.parametrize("lang", BATCH6_LANGUAGES)
    def test_language_in_registry(self, lang):
        assert lang in LANGUAGE_REGISTRY, f"{lang} not in LANGUAGE_REGISTRY"

    def test_registry_count(self):
        """Registry should have at least 62 languages (55 existing + 7 new)."""
        assert len(LANGUAGE_REGISTRY) >= 62
