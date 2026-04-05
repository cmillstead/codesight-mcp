"""Tests for batch 5 language support: fortran, cmake, matlab, cuda, v, gleam, odin, gdscript, verilog, vhdl.

Verifies symbol extraction, extension mapping, and registry completeness
for systems, scientific, HDL, and gamedev languages.
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
# Fortran tests
# ---------------------------------------------------------------------------


class TestFortranSymbols:
    """Fortran: subroutine, function, and program extraction."""

    def test_fortran_subroutine(self, tmp_path):
        source = """\
subroutine greet(name)
  character(*), intent(in) :: name
  print *, 'Hello, ', name
end subroutine
"""
        symbols = parse_file(source, str(tmp_path / "test.f90"), "fortran")
        names = _symbol_names(symbols)
        assert "greet" in names
        greet = _symbol_by_name(symbols, "greet")
        assert greet.kind == "function"

    def test_fortran_program(self, tmp_path):
        source = """\
program hello
  implicit none
  print *, 'Hello'
end program
"""
        symbols = parse_file(source, str(tmp_path / "test.f90"), "fortran")
        names = _symbol_names(symbols)
        assert "hello" in names
        hello = _symbol_by_name(symbols, "hello")
        assert hello.kind == "class"

    def test_fortran_program_with_subroutine(self, tmp_path):
        source = """\
program main
  implicit none
  call greet()
contains
  subroutine greet()
    print *, 'Hello'
  end subroutine
end program
"""
        symbols = parse_file(source, str(tmp_path / "test.f90"), "fortran")
        names = _symbol_names(symbols)
        assert "main" in names
        assert "greet" in names
        main_sym = _symbol_by_name(symbols, "main")
        assert main_sym.kind == "class"
        greet_sym = _symbol_by_name(symbols, "greet")
        assert greet_sym.kind in ("function", "method")


# ---------------------------------------------------------------------------
# CMake tests
# ---------------------------------------------------------------------------


class TestCmakeSymbols:
    """CMake: function_def and macro_def extraction."""

    def test_cmake_function(self, tmp_path):
        source = """\
function(my_func ARG1 ARG2)
  message(STATUS "Hello")
endfunction()
"""
        symbols = parse_file(source, str(tmp_path / "test.cmake"), "cmake")
        names = _symbol_names(symbols)
        assert "my_func" in names
        func = _symbol_by_name(symbols, "my_func")
        assert func.kind == "function"

    def test_cmake_macro(self, tmp_path):
        source = """\
macro(my_macro ARG1)
  message(STATUS "Macro")
endmacro()
"""
        symbols = parse_file(source, str(tmp_path / "test.cmake"), "cmake")
        names = _symbol_names(symbols)
        assert "my_macro" in names
        macro = _symbol_by_name(symbols, "my_macro")
        assert macro.kind == "function"

    def test_cmake_quoted_name(self, tmp_path):
        source = """\
function("quoted_func" ARG1)
  message(STATUS "Hello")
endfunction()
"""
        symbols = parse_file(source, str(tmp_path / "test.cmake"), "cmake")
        names = _symbol_names(symbols)
        assert "quoted_func" in names


# ---------------------------------------------------------------------------
# MATLAB tests
# ---------------------------------------------------------------------------


class TestMatlabSymbols:
    """MATLAB: function_definition extraction."""

    def test_matlab_function(self, tmp_path):
        source = """\
function result = compute(x)
  result = x * 2;
end
"""
        symbols = parse_file(source, str(tmp_path / "test.m"), "matlab")
        names = _symbol_names(symbols)
        assert "compute" in names
        compute = _symbol_by_name(symbols, "compute")
        assert compute.kind == "function"


# ---------------------------------------------------------------------------
# CUDA tests
# ---------------------------------------------------------------------------


class TestCudaSymbols:
    """CUDA: function_definition and struct_specifier extraction."""

    def test_cuda_function(self, tmp_path):
        source = """\
__global__ void kernel_add(int *a, int *b, int *c) {
    int i = threadIdx.x;
    c[i] = a[i] + b[i];
}
"""
        symbols = parse_file(source, str(tmp_path / "test.cu"), "cuda")
        names = _symbol_names(symbols)
        assert "kernel_add" in names
        kernel = _symbol_by_name(symbols, "kernel_add")
        assert kernel.kind == "function"

    def test_cuda_pointer_declarator(self, tmp_path):
        source = """\
int *get_data() {
    return NULL;
}
"""
        symbols = parse_file(source, str(tmp_path / "test.cu"), "cuda")
        names = _symbol_names(symbols)
        assert "get_data" in names

    def test_cuda_struct_is_type(self, tmp_path):
        source = """\
struct CudaConfig {
    int device_id;
    int block_size;
};
"""
        symbols = parse_file(source, str(tmp_path / "test.cu"), "cuda")
        names = _symbol_names(symbols)
        assert "CudaConfig" in names
        config = _symbol_by_name(symbols, "CudaConfig")
        assert config.kind == "type", f"Expected 'type' but got '{config.kind}'"


# ---------------------------------------------------------------------------
# V language tests
# ---------------------------------------------------------------------------


class TestVSymbols:
    """V: function_declaration and struct_declaration extraction."""

    def test_v_function_and_struct(self, tmp_path):
        source = """\
fn hello() {
    println('Hello')
}

struct Point {
    x int
    y int
}
"""
        symbols = parse_file(source, str(tmp_path / "test.vv"), "v")
        names = _symbol_names(symbols)
        assert "hello" in names
        assert "Point" in names
        hello = _symbol_by_name(symbols, "hello")
        assert hello.kind == "function"
        point = _symbol_by_name(symbols, "Point")
        assert point.kind == "class"


# ---------------------------------------------------------------------------
# Gleam tests
# ---------------------------------------------------------------------------


class TestGleamSymbols:
    """Gleam: function extraction."""

    def test_gleam_function(self, tmp_path):
        source = """\
pub fn hello() {
  io.println("Hello")
}
"""
        symbols = parse_file(source, str(tmp_path / "test.gleam"), "gleam")
        names = _symbol_names(symbols)
        assert "hello" in names
        hello = _symbol_by_name(symbols, "hello")
        assert hello.kind == "function"


# ---------------------------------------------------------------------------
# Odin tests
# ---------------------------------------------------------------------------


class TestOdinSymbols:
    """Odin: procedure_declaration extraction."""

    def test_odin_procedure(self, tmp_path):
        source = """\
package main

hello :: proc() {
    fmt.println("Hello")
}
"""
        symbols = parse_file(source, str(tmp_path / "test.odin"), "odin")
        names = _symbol_names(symbols)
        assert "hello" in names
        hello = _symbol_by_name(symbols, "hello")
        assert hello.kind == "function"


# ---------------------------------------------------------------------------
# GDScript tests
# ---------------------------------------------------------------------------


class TestGdscriptSymbols:
    """GDScript: function_definition and variable_statement extraction."""

    def test_gdscript_function(self, tmp_path):
        source = """\
func hello():
    pass
"""
        symbols = parse_file(source, str(tmp_path / "test.gd"), "gdscript")
        names = _symbol_names(symbols)
        assert "hello" in names
        hello = _symbol_by_name(symbols, "hello")
        assert hello.kind == "function"

    def test_gdscript_variable(self, tmp_path):
        source = """\
var speed = 100
"""
        symbols = parse_file(source, str(tmp_path / "test.gd"), "gdscript")
        names = _symbol_names(symbols)
        assert "speed" in names
        speed = _symbol_by_name(symbols, "speed")
        assert speed.kind == "constant"


# ---------------------------------------------------------------------------
# Verilog tests
# ---------------------------------------------------------------------------


class TestVerilogSymbols:
    """Verilog: module_declaration extraction."""

    def test_verilog_module(self, tmp_path):
        source = """\
module counter(input clk, input rst, output reg [7:0] count);
    always @(posedge clk) begin
        if (rst) count <= 0;
        else count <= count + 1;
    end
endmodule
"""
        symbols = parse_file(source, str(tmp_path / "test.sv"), "verilog")
        names = _symbol_names(symbols)
        assert "counter" in names
        counter = _symbol_by_name(symbols, "counter")
        assert counter.kind == "class"


# ---------------------------------------------------------------------------
# VHDL tests
# ---------------------------------------------------------------------------


class TestVhdlSymbols:
    """VHDL: entity_declaration and architecture_body extraction."""

    def test_vhdl_entity(self, tmp_path):
        source = """\
entity counter is
    port (
        clk : in std_logic;
        count : out integer
    );
end entity;
"""
        symbols = parse_file(source, str(tmp_path / "test.vhd"), "vhdl")
        names = _symbol_names(symbols)
        assert "counter" in names
        counter = _symbol_by_name(symbols, "counter")
        assert counter.kind == "class"

    def test_vhdl_architecture(self, tmp_path):
        source = """\
architecture behavioral of counter is
begin
    process(clk)
    begin
    end process;
end architecture;
"""
        symbols = parse_file(source, str(tmp_path / "test.vhd"), "vhdl")
        names = _symbol_names(symbols)
        assert "behavioral" in names
        arch = _symbol_by_name(symbols, "behavioral")
        assert arch.kind == "class"


# ---------------------------------------------------------------------------
# Extension mapping tests
# ---------------------------------------------------------------------------


BATCH5_EXTENSIONS = [
    (".f90", "fortran"),
    (".f95", "fortran"),
    (".f03", "fortran"),
    (".f08", "fortran"),
    (".f", "fortran"),
    (".cmake", "cmake"),
    (".m", "matlab"),
    (".cu", "cuda"),
    (".cuh", "cuda"),
    (".vv", "v"),
    (".gleam", "gleam"),
    (".odin", "odin"),
    (".gd", "gdscript"),
    (".sv", "verilog"),
    (".vhd", "vhdl"),
    (".vhdl", "vhdl"),
]


class TestBatch5Extensions:
    """Verify extension -> language mapping for batch 5 languages."""

    @pytest.mark.parametrize("ext,expected_lang", BATCH5_EXTENSIONS, ids=[e[0] for e in BATCH5_EXTENSIONS])
    def test_extension_mapping(self, ext, expected_lang):
        assert LANGUAGE_EXTENSIONS[ext] == expected_lang


class TestBatch5Registry:
    """Verify all batch 5 languages are in the registry."""

    BATCH5_LANGUAGES = [
        "fortran", "cmake", "matlab", "cuda", "v", "gleam",
        "odin", "gdscript", "verilog", "vhdl",
    ]

    @pytest.mark.parametrize("lang", BATCH5_LANGUAGES)
    def test_language_in_registry(self, lang):
        assert lang in LANGUAGE_REGISTRY, f"{lang} not in LANGUAGE_REGISTRY"

    def test_registry_count(self):
        """Registry should have at least 55 languages (45 existing + 10 new)."""
        assert len(LANGUAGE_REGISTRY) >= 55
