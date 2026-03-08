"""Tests for the 6 new language parsers: C, C++, C#, Ruby, Swift, Kotlin."""

import pytest

from codesight_mcp.parser.extractor import parse_file


class TestCParser:
    def test_function(self):
        code = 'void greet(const char* name) {\n    printf("Hello");\n}\n'
        symbols = parse_file(code, "test.c", "c")
        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) >= 1
        assert funcs[0].name == "greet"

    def test_struct(self):
        code = "struct Point {\n    int x;\n    int y;\n};\n"
        symbols = parse_file(code, "test.c", "c")
        types = [s for s in symbols if s.kind == "type"]
        assert any(s.name == "Point" for s in types)

    def test_typedef(self):
        code = "typedef struct { int x; } Point;\n"
        symbols = parse_file(code, "test.c", "c")
        types = [s for s in symbols if s.kind == "type"]
        assert any(s.name == "Point" for s in types)

    def test_include(self):
        code = '#include <stdio.h>\n#include "myheader.h"\n\nvoid foo() {}\n'
        symbols = parse_file(code, "test.c", "c")
        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) >= 1
        assert "stdio.h" in funcs[0].imports

    def test_call_extraction(self):
        code = "void foo() {\n    bar();\n    baz(1, 2);\n}\n"
        symbols = parse_file(code, "test.c", "c")
        funcs = [s for s in symbols if s.kind == "function"]
        assert "bar" in funcs[0].calls
        assert "baz" in funcs[0].calls


class TestCppParser:
    def test_class(self):
        code = "class Animal {\npublic:\n    void speak() {}\n};\n"
        symbols = parse_file(code, "test.cpp", "cpp")
        classes = [s for s in symbols if s.kind == "class"]
        assert any(s.name == "Animal" for s in classes)

    def test_function(self):
        code = "int add(int a, int b) {\n    return a + b;\n}\n"
        symbols = parse_file(code, "test.cpp", "cpp")
        funcs = [s for s in symbols if s.kind == "function"]
        assert any(s.name == "add" for s in funcs)

    def test_method_inside_class(self):
        code = "class Foo {\npublic:\n    void bar() { baz(); }\n};\n"
        symbols = parse_file(code, "test.cpp", "cpp")
        methods = [s for s in symbols if s.kind == "method"]
        assert any(s.name == "bar" for s in methods)

    def test_inheritance(self):
        code = "class Dog : public Animal {\npublic:\n    void speak() {}\n};\n"
        symbols = parse_file(code, "test.cpp", "cpp")
        classes = [s for s in symbols if s.kind == "class"]
        dog = next((s for s in classes if s.name == "Dog"), None)
        assert dog is not None
        assert "Animal" in dog.inherits_from


class TestCSharpParser:
    def test_class(self):
        code = "class User {\n    public void Save() {}\n}\n"
        symbols = parse_file(code, "test.cs", "c_sharp")
        classes = [s for s in symbols if s.kind == "class"]
        assert any(s.name == "User" for s in classes)

    def test_method(self):
        code = "class Foo {\n    public int Add(int a, int b) { return a + b; }\n}\n"
        symbols = parse_file(code, "test.cs", "c_sharp")
        methods = [s for s in symbols if s.kind == "method"]
        assert any(s.name == "Add" for s in methods)

    def test_interface(self):
        code = "interface ISerializable {\n    void Serialize();\n}\n"
        symbols = parse_file(code, "test.cs", "c_sharp")
        types = [s for s in symbols if s.kind == "type"]
        assert any(s.name == "ISerializable" for s in types)

    def test_using(self):
        code = "using System;\n\nclass Foo {\n    public void Bar() {}\n}\n"
        symbols = parse_file(code, "test.cs", "c_sharp")
        classes = [s for s in symbols if s.kind == "class"]
        assert len(classes) >= 1

    def test_inheritance(self):
        code = "class Admin : User {\n    public void Promote() {}\n}\n"
        symbols = parse_file(code, "test.cs", "c_sharp")
        classes = [s for s in symbols if s.kind == "class"]
        admin = next((s for s in classes if s.name == "Admin"), None)
        assert admin is not None
        assert "User" in admin.inherits_from


class TestRubyParser:
    def test_method(self):
        code = "def greet(name)\n  puts name\nend\n"
        symbols = parse_file(code, "test.rb", "ruby")
        funcs = [s for s in symbols if s.kind == "function"]
        assert any(s.name == "greet" for s in funcs)

    def test_class(self):
        code = "class User\n  def save\n    puts 'saved'\n  end\nend\n"
        symbols = parse_file(code, "test.rb", "ruby")
        classes = [s for s in symbols if s.kind == "class"]
        assert any(s.name == "User" for s in classes)

    def test_module(self):
        code = "module Serializable\n  def serialize\n  end\nend\n"
        symbols = parse_file(code, "test.rb", "ruby")
        types = [s for s in symbols if s.kind == "type"]
        assert any(s.name == "Serializable" for s in types)

    def test_inheritance(self):
        code = "class Admin < User\n  def promote\n  end\nend\n"
        symbols = parse_file(code, "test.rb", "ruby")
        classes = [s for s in symbols if s.kind == "class"]
        admin = next((s for s in classes if s.name == "Admin"), None)
        assert admin is not None
        assert "User" in admin.inherits_from

    def test_call_extraction(self):
        code = "def foo\n  bar()\n  obj.baz()\nend\n"
        symbols = parse_file(code, "test.rb", "ruby")
        funcs = [s for s in symbols if s.kind == "function" and s.name == "foo"]
        assert len(funcs) == 1
        assert "bar" in funcs[0].calls or "baz" in funcs[0].calls


class TestSwiftParser:
    def test_function(self):
        code = "func greet(name: String) -> String {\n    return name\n}\n"
        symbols = parse_file(code, "test.swift", "swift")
        funcs = [s for s in symbols if s.kind == "function"]
        assert any(s.name == "greet" for s in funcs)

    def test_class(self):
        code = "class User {\n    func save() {}\n}\n"
        symbols = parse_file(code, "test.swift", "swift")
        classes = [s for s in symbols if s.kind == "class"]
        assert any(s.name == "User" for s in classes)

    def test_protocol(self):
        code = "protocol Serializable {\n    func serialize()\n}\n"
        symbols = parse_file(code, "test.swift", "swift")
        types = [s for s in symbols if s.kind == "type"]
        assert any(s.name == "Serializable" for s in types)

    def test_import(self):
        code = "import Foundation\n\nfunc foo() {}\n"
        symbols = parse_file(code, "test.swift", "swift")
        funcs = [s for s in symbols if s.kind == "function"]
        assert len(funcs) >= 1


class TestKotlinParser:
    def test_function(self):
        code = "fun greet(name: String): String {\n    return name\n}\n"
        symbols = parse_file(code, "test.kt", "kotlin")
        funcs = [s for s in symbols if s.kind == "function"]
        assert any(s.name == "greet" for s in funcs)

    def test_class(self):
        code = "class User {\n    fun save() {}\n}\n"
        symbols = parse_file(code, "test.kt", "kotlin")
        classes = [s for s in symbols if s.kind == "class"]
        assert any(s.name == "User" for s in classes)

    def test_object(self):
        code = "object Registry {\n    fun lookup(key: String): String = key\n}\n"
        symbols = parse_file(code, "test.kt", "kotlin")
        types = [s for s in symbols if s.kind == "type"]
        assert any(s.name == "Registry" for s in types)

    def test_inheritance(self):
        code = "open class Base\nclass Derived : Base() {\n    fun foo() {}\n}\n"
        symbols = parse_file(code, "test.kt", "kotlin")
        classes = [s for s in symbols if s.kind == "class"]
        derived = next((s for s in classes if s.name == "Derived"), None)
        assert derived is not None
        assert "Base" in derived.inherits_from
