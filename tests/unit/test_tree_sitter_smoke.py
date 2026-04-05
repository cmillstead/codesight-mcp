"""Tree-sitter grammar smoke tests (RC-015, AEGIS remediation).

Verify every supported language grammar loads and can parse a minimal
source file.  These tests catch broken grammars after tree-sitter
dependency upgrades before they reach production.
"""

import pytest
from codesight_mcp.parser.extractor import _get_parser, parse_file, SUPPORTED_LANGUAGES


# ── Minimal source snippets per language ──────────────────────────────
# Each tuple: (language, extension, source, expected_symbol_kind)

LANGUAGE_SMOKE_CASES = [
    ("python", ".py", "def hello(): pass", "function"),
    ("javascript", ".js", "function hello() {}", "function"),
    ("typescript", ".ts", "function hello(): void {}", "function"),
    ("go", ".go", "package main\nfunc hello() {}", "function"),
    ("rust", ".rs", "fn hello() {}", "function"),
    ("java", ".java", "class Hello { void greet() {} }", "class"),
    ("php", ".php", "<?php\nfunction hello() {}", "function"),
    ("c", ".c", "int hello() { return 0; }", "function"),
    ("cpp", ".cpp", "int hello() { return 0; }", "function"),
    ("c_sharp", ".cs", "class Hello { void Greet() {} }", "class"),
    ("ruby", ".rb", "def hello\nend", "function"),
    ("swift", ".swift", "func hello() {}", "function"),
    ("kotlin", ".kt", "fun hello() {}", "function"),
    ("dart", ".dart", "void hello() {}", "function"),
    ("perl", ".pl", "sub hello {}", "function"),
    ("css", ".css", ".container { color: red; }", "class"),
    ("scss", ".scss", "$primary: blue;", "constant"),
    ("html", ".html", "<html><body>hi</body></html>", "class"),
    ("xml", ".xml", "<root><child/></root>", "class"),
    ("yaml", ".yaml", "key: value", "constant"),
    ("json", ".json", '{"key": "value"}', "constant"),
    ("toml", ".toml", 'name = "val"', "constant"),
    ("make", ".mk", "all: main.o\n\tgcc -o all main.o", "function"),
    ("lua", ".lua", "function hello() end", "function"),
    ("bash", ".sh", "hello() { echo hi; }", "function"),
    ("scala", ".scala", "object Hello { def greet(): Unit = {} }", "class"),
    ("r", ".r", "hello <- function() {}", "function"),
    ("elixir", ".ex", "defmodule Hello do\nend", "class"),
    ("julia", ".jl", "function hello() end", "function"),
    ("clojure", ".clj", "(defn hello [] nil)", "function"),
    ("nim", ".nim", "proc hello() = discard", "function"),
    ("haskell", ".hs", "data Color = Red | Green | Blue", "class"),
    ("erlang", ".erl", "-module(hello).\nhello() -> ok.", "function"),
    ("zig", ".zig", "pub fn hello() void {}", "function"),
    ("d", ".d", "void hello() {}", "function"),
    ("objc", ".mm", "@interface Hello @end\n@implementation Hello @end", "class"),
    ("ocaml", ".ml", "let hello = 1", "function"),
    ("fsharp", ".fs", "type Color = Red | Green | Blue", "type"),
    ("elm", ".elm", "hello = 1", "function"),
    ("sql", ".sql", "CREATE TABLE hello (id INT);", "class"),
    ("powershell", ".ps1", "function Hello { }", "function"),
    ("solidity", ".sol", "contract Hello { }", "class"),
    ("hcl", ".tf", 'resource "aws_instance" "hello" {}', "class"),
    ("proto", ".proto", "message Hello {}", "class"),
    ("graphql", ".graphql", "type Hello { id: ID! }", "class"),
    ("fortran", ".f90", "program hello\nend program", "class"),
    ("cmake", ".cmake", "function(my_func)\nendfunction()", "function"),
    ("matlab", ".m", "function result = compute(x)\n  result = x * 2;\nend", "function"),
    ("cuda", ".cu", "void hello() {}", "function"),
    ("v", ".vv", "fn hello() {}", "function"),
    ("gleam", ".gleam", "pub fn hello() {}", "function"),
    ("odin", ".odin", "package main\nhello :: proc() {}", "function"),
    ("gdscript", ".gd", "func hello():\n  pass", "function"),
    ("verilog", ".sv", "module counter(input clk);\nendmodule", "class"),
    ("vhdl", ".vhd", "entity counter is\nend entity;", "class"),
    ("ada", ".adb", "procedure Hello is\nbegin\n  null;\nend Hello;", "function"),
    ("pascal", ".pas", "program Hello;\nbegin\nend.", "class"),
    ("commonlisp", ".lisp", "(defun hello (x) (+ x 1))", "function"),
    ("scheme", ".scm", "(define (hello x) (+ x 1))", "function"),
    ("racket", ".rkt", "(define (hello x) (+ x 1))", "function"),
    ("tcl", ".tcl", "proc hello {name} { puts $name }", "function"),
    ("dockerfile", ".dockerfile", "FROM ubuntu:22.04", "class"),
    ("glsl", ".glsl", "void main() {}", "function"),
    ("hlsl", ".hlsl", "float4 main() : SV_Target { return float4(1,1,1,1); }", "function"),
    ("wgsl", ".wgsl", "fn vs_main() -> vec4f { return vec4f(0.0); }", "function"),
    ("nix", ".nix", "let\n  hello = 42;\nin hello", "constant"),
]


class TestGrammarLoads:
    """Verify each tree-sitter grammar can be imported and a parser created."""

    @pytest.mark.parametrize(
        "lang",
        sorted(SUPPORTED_LANGUAGES),
        ids=sorted(SUPPORTED_LANGUAGES),
    )
    def test_parser_creation(self, lang: str) -> None:
        parser = _get_parser(lang)
        assert parser is not None, f"Grammar for '{lang}' failed to load"


class TestMinimalParse:
    """Verify each language can parse a minimal source file and extract symbols."""

    @pytest.mark.parametrize(
        "lang,ext,source,expected_kind",
        LANGUAGE_SMOKE_CASES,
        ids=[case[0] for case in LANGUAGE_SMOKE_CASES],
    )
    def test_grammar_parses_minimal_source(
        self,
        tmp_path,
        lang: str,
        ext: str,
        source: str,
        expected_kind: str,
    ) -> None:
        filename = str(tmp_path / f"smoke{ext}")
        symbols = parse_file(source, filename, lang)
        assert len(symbols) >= 1, (
            f"Expected at least 1 symbol from {lang} source, got {len(symbols)}"
        )
        kinds = {s.kind for s in symbols}
        assert expected_kind in kinds, (
            f"Expected kind '{expected_kind}' in {kinds} for {lang}"
        )


class TestEdgeCases:
    """Verify graceful handling of unsupported and empty inputs."""

    def test_unsupported_extension_returns_empty(self, tmp_path) -> None:
        """An unrecognized language name returns empty list, not a crash."""
        symbols = parse_file("some content", str(tmp_path / "file.xyz"), "brainfuck")
        assert symbols == []

    def test_empty_file_returns_empty(self, tmp_path) -> None:
        """An empty source string returns empty list, not a crash."""
        symbols = parse_file("", str(tmp_path / "empty.py"), "python")
        assert symbols == []

    def test_unsupported_language_in_get_parser_raises(self) -> None:
        """_get_parser raises ValueError for languages outside the allow-list."""
        with pytest.raises(ValueError, match="Unsupported language"):
            _get_parser("brainfuck")


class TestSmokeCoverage:
    """Ensure smoke cases stay in sync with SUPPORTED_LANGUAGES."""

    def test_smoke_cases_cover_all_languages(self):
        smoke_langs = {case[0] for case in LANGUAGE_SMOKE_CASES}
        assert smoke_langs == SUPPORTED_LANGUAGES, (
            f"Missing smoke cases: {SUPPORTED_LANGUAGES - smoke_langs}"
        )
