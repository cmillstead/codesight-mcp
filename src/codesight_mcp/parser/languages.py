"""Language registry with LanguageSpec definitions for all supported languages."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LanguageSpec:
    """Specification for extracting symbols from a language's AST."""
    # tree-sitter language name (for tree-sitter-language-pack)
    ts_language: str

    # Node types that represent extractable symbols
    # Maps node_type -> symbol kind
    symbol_node_types: dict[str, str]

    # How to extract the symbol name from a node
    # Maps node_type -> child field name containing the name
    name_fields: dict[str, str]

    # How to extract parameters/signature beyond the name
    # Maps node_type -> child field name for parameters
    param_fields: dict[str, str]

    # Return type extraction (if language supports it)
    # Maps node_type -> child field name for return type
    return_type_fields: dict[str, str]

    # Docstring extraction strategy
    # "next_sibling_string" = Python (expression_statement after def)
    # "first_child_comment" = JS/TS (/** */ before function)
    # "preceding_comment" = Go/Rust/Java (// or /* */ before decl)
    docstring_strategy: str

    # Decorator/attribute node type (if any)
    decorator_node_type: Optional[str]

    # Node types that indicate nesting (methods inside classes)
    container_node_types: list[str]

    # Additional extraction: constants, type aliases
    constant_patterns: list[str]   # Node types for constants
    type_patterns: list[str]       # Node types for type definitions

    # Relationship tracking: AST node types for call graphs, imports, inheritance
    call_node_types: list[str] = field(default_factory=list)          # Function/method call node types
    import_node_types: list[str] = field(default_factory=list)        # Import statement node types
    inheritance_fields: list[str] = field(default_factory=list)       # AST fields for superclass/parent refs
    implementation_fields: list[str] = field(default_factory=list)    # AST fields for interface implementations


# File extension to language mapping
LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".cs": "c_sharp",
    ".rb": "ruby",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
}


# Python specification
PYTHON_SPEC = LanguageSpec(
    ts_language="python",
    symbol_node_types={
        "function_definition": "function",
        "class_definition": "class",
    },
    name_fields={
        "function_definition": "name",
        "class_definition": "name",
    },
    param_fields={
        "function_definition": "parameters",
    },
    return_type_fields={
        "function_definition": "return_type",
    },
    docstring_strategy="next_sibling_string",
    decorator_node_type="decorator",
    container_node_types=["class_definition"],
    constant_patterns=["assignment"],
    type_patterns=["type_alias_statement"],
    call_node_types=["call"],
    import_node_types=["import_statement", "import_from_statement"],
    inheritance_fields=["argument_list"],
)


# JavaScript specification
JAVASCRIPT_SPEC = LanguageSpec(
    ts_language="javascript",
    symbol_node_types={
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
        "arrow_function": "function",
        "generator_function_declaration": "function",
    },
    name_fields={
        "function_declaration": "name",
        "class_declaration": "name",
        "method_definition": "name",
    },
    param_fields={
        "function_declaration": "parameters",
        "method_definition": "parameters",
        "arrow_function": "parameters",
    },
    return_type_fields={},
    docstring_strategy="preceding_comment",
    decorator_node_type=None,
    container_node_types=["class_declaration", "class"],
    constant_patterns=["lexical_declaration"],
    type_patterns=[],
    call_node_types=["call_expression"],
    import_node_types=["import_statement"],
    inheritance_fields=["class_heritage"],
)


# TypeScript specification
TYPESCRIPT_SPEC = LanguageSpec(
    ts_language="typescript",
    symbol_node_types={
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
        "arrow_function": "function",
        "interface_declaration": "type",
        "type_alias_declaration": "type",
        "enum_declaration": "type",
    },
    name_fields={
        "function_declaration": "name",
        "class_declaration": "name",
        "method_definition": "name",
        "interface_declaration": "name",
        "type_alias_declaration": "name",
        "enum_declaration": "name",
    },
    param_fields={
        "function_declaration": "parameters",
        "method_definition": "parameters",
        "arrow_function": "parameters",
    },
    return_type_fields={
        "function_declaration": "return_type",
        "method_definition": "return_type",
        "arrow_function": "return_type",
    },
    docstring_strategy="preceding_comment",
    decorator_node_type="decorator",
    container_node_types=["class_declaration", "class"],
    constant_patterns=["lexical_declaration"],
    type_patterns=["interface_declaration", "type_alias_declaration", "enum_declaration"],
    call_node_types=["call_expression"],
    import_node_types=["import_statement"],
    inheritance_fields=["class_heritage"],
    implementation_fields=["class_heritage"],
)


# Go specification
GO_SPEC = LanguageSpec(
    ts_language="go",
    symbol_node_types={
        "function_declaration": "function",
        "method_declaration": "method",
        "type_declaration": "type",
    },
    name_fields={
        "function_declaration": "name",
        "method_declaration": "name",
        "type_declaration": "name",
    },
    param_fields={
        "function_declaration": "parameters",
        "method_declaration": "parameters",
    },
    return_type_fields={
        "function_declaration": "result",
        "method_declaration": "result",
    },
    docstring_strategy="preceding_comment",
    decorator_node_type=None,
    container_node_types=[],
    constant_patterns=["const_declaration"],
    type_patterns=["type_declaration"],
    call_node_types=["call_expression"],
    import_node_types=["import_declaration"],
)


# Rust specification
RUST_SPEC = LanguageSpec(
    ts_language="rust",
    symbol_node_types={
        "function_item": "function",
        "struct_item": "type",
        "enum_item": "type",
        "trait_item": "type",
        "impl_item": "class",
        "type_item": "type",
    },
    name_fields={
        "function_item": "name",
        "struct_item": "name",
        "enum_item": "name",
        "trait_item": "name",
        "type_item": "name",
    },
    param_fields={
        "function_item": "parameters",
    },
    return_type_fields={
        "function_item": "return_type",
    },
    docstring_strategy="preceding_comment",
    decorator_node_type="attribute_item",
    container_node_types=["impl_item", "trait_item"],
    constant_patterns=["const_item", "static_item"],
    type_patterns=["struct_item", "enum_item", "trait_item", "type_item"],
    call_node_types=["call_expression", "macro_invocation"],
    import_node_types=["use_declaration"],
    inheritance_fields=["trait_bounds"],
)


# Java specification
JAVA_SPEC = LanguageSpec(
    ts_language="java",
    symbol_node_types={
        "method_declaration": "method",
        "constructor_declaration": "method",
        "class_declaration": "class",
        "interface_declaration": "type",
        "enum_declaration": "type",
    },
    name_fields={
        "method_declaration": "name",
        "constructor_declaration": "name",
        "class_declaration": "name",
        "interface_declaration": "name",
        "enum_declaration": "name",
    },
    param_fields={
        "method_declaration": "parameters",
        "constructor_declaration": "parameters",
    },
    return_type_fields={
        "method_declaration": "type",
    },
    docstring_strategy="preceding_comment",
    decorator_node_type="marker_annotation",
    container_node_types=["class_declaration", "interface_declaration", "enum_declaration"],
    constant_patterns=["field_declaration"],
    type_patterns=["interface_declaration", "enum_declaration"],
    call_node_types=["method_invocation"],
    import_node_types=["import_declaration"],
    inheritance_fields=["superclass"],
    implementation_fields=["super_interfaces"],
)


# PHP specification
PHP_SPEC = LanguageSpec(
    ts_language="php",
    symbol_node_types={
        "function_definition": "function",
        "class_declaration": "class",
        "method_declaration": "method",
        "interface_declaration": "type",
        "trait_declaration": "type",
        "enum_declaration": "type",
    },
    name_fields={
        "function_definition": "name",
        "class_declaration": "name",
        "method_declaration": "name",
        "interface_declaration": "name",
        "trait_declaration": "name",
        "enum_declaration": "name",
    },
    param_fields={
        "function_definition": "parameters",
        "method_declaration": "parameters",
    },
    return_type_fields={
        "function_definition": "return_type",
        "method_declaration": "return_type",
    },
    docstring_strategy="preceding_comment",
    decorator_node_type="attribute",  # PHP 8 #[Attribute] syntax
    container_node_types=["class_declaration", "trait_declaration", "interface_declaration"],
    constant_patterns=["const_declaration"],
    type_patterns=["interface_declaration", "trait_declaration", "enum_declaration"],
    call_node_types=["function_call_expression", "member_call_expression"],
    import_node_types=["namespace_use_declaration"],
    inheritance_fields=["base_clause"],
    implementation_fields=["class_interface_clause"],
)


# C specification
C_SPEC = LanguageSpec(
    ts_language="c",
    symbol_node_types={
        "function_definition": "function",
        "struct_specifier": "type",
        "enum_specifier": "type",
        "type_definition": "type",
    },
    name_fields={
        "struct_specifier": "name",
        "enum_specifier": "name",
        # function_definition and type_definition use declarator — handled in extractor
    },
    param_fields={},  # parameters are inside function_declarator — handled in extractor
    return_type_fields={
        "function_definition": "type",
    },
    docstring_strategy="preceding_comment",
    decorator_node_type=None,
    container_node_types=["struct_specifier"],
    constant_patterns=["preproc_def"],
    type_patterns=["type_definition", "struct_specifier", "enum_specifier"],
    call_node_types=["call_expression"],
    import_node_types=["preproc_include"],
)


# C++ specification
CPP_SPEC = LanguageSpec(
    ts_language="cpp",
    symbol_node_types={
        "function_definition": "function",
        "class_specifier": "class",
        "struct_specifier": "type",
        "enum_specifier": "type",
        "namespace_definition": "type",
    },
    name_fields={
        "class_specifier": "name",
        "struct_specifier": "name",
        "enum_specifier": "name",
        "namespace_definition": "name",
        # function_definition uses declarator — handled in extractor
    },
    param_fields={},  # parameters are inside function_declarator — handled in extractor
    return_type_fields={
        "function_definition": "type",
    },
    docstring_strategy="preceding_comment",
    decorator_node_type=None,
    container_node_types=["class_specifier", "struct_specifier", "namespace_definition"],
    constant_patterns=["preproc_def"],
    type_patterns=["class_specifier", "struct_specifier", "enum_specifier"],
    call_node_types=["call_expression"],
    import_node_types=["preproc_include", "using_declaration"],
    inheritance_fields=["base_class_clause"],
)


# C# specification
CSHARP_SPEC = LanguageSpec(
    ts_language="c_sharp",
    symbol_node_types={
        "method_declaration": "method",
        "constructor_declaration": "method",
        "class_declaration": "class",
        "struct_declaration": "type",
        "interface_declaration": "type",
        "enum_declaration": "type",
        "namespace_declaration": "type",
    },
    name_fields={
        "method_declaration": "name",
        "constructor_declaration": "name",
        "class_declaration": "name",
        "struct_declaration": "name",
        "interface_declaration": "name",
        "enum_declaration": "name",
        "namespace_declaration": "name",
    },
    param_fields={
        "method_declaration": "parameters",
        "constructor_declaration": "parameters",
    },
    return_type_fields={
        "method_declaration": "returns",
    },
    docstring_strategy="preceding_comment",
    decorator_node_type="attribute_list",
    container_node_types=["class_declaration", "struct_declaration", "interface_declaration", "namespace_declaration"],
    constant_patterns=["field_declaration"],
    type_patterns=["class_declaration", "struct_declaration", "interface_declaration", "enum_declaration"],
    call_node_types=["invocation_expression"],
    import_node_types=["using_directive"],
    inheritance_fields=["base_list"],
    implementation_fields=["base_list"],
)


# Ruby specification
RUBY_SPEC = LanguageSpec(
    ts_language="ruby",
    symbol_node_types={
        "method": "function",
        "singleton_method": "function",
        "class": "class",
        "module": "type",
    },
    name_fields={
        "method": "name",
        "singleton_method": "name",
        "class": "name",
        "module": "name",
    },
    param_fields={
        "method": "parameters",
        "singleton_method": "parameters",
    },
    return_type_fields={},
    docstring_strategy="preceding_comment",
    decorator_node_type=None,
    container_node_types=["class", "module"],
    constant_patterns=["assignment"],
    type_patterns=["class", "module"],
    call_node_types=["call"],
    import_node_types=[],  # Ruby uses require() calls — not a distinct node type
    inheritance_fields=["superclass"],
)


# Swift specification
SWIFT_SPEC = LanguageSpec(
    ts_language="swift",
    symbol_node_types={
        "function_declaration": "function",
        "class_declaration": "class",
        "protocol_declaration": "type",
    },
    name_fields={
        "function_declaration": "name",
        "class_declaration": "name",
        "protocol_declaration": "name",
    },
    param_fields={},  # Swift parameters are positional children — partial extraction via signature
    return_type_fields={},  # return type is after -> token, positional
    docstring_strategy="preceding_comment",
    decorator_node_type="attribute",
    container_node_types=["class_declaration", "protocol_declaration"],
    constant_patterns=["property_declaration"],
    type_patterns=["class_declaration", "protocol_declaration"],
    call_node_types=["call_expression"],
    import_node_types=["import_declaration"],
    inheritance_fields=["inheritance_specifier"],
)


# Kotlin specification
KOTLIN_SPEC = LanguageSpec(
    ts_language="kotlin",
    symbol_node_types={
        "function_declaration": "function",
        "class_declaration": "class",
        "object_declaration": "type",
    },
    name_fields={
        "function_declaration": "name",
        "class_declaration": "name",
        "object_declaration": "name",
    },
    param_fields={},  # Kotlin parameters use function_value_parameters — partial extraction via signature
    return_type_fields={},  # return type is positional
    docstring_strategy="preceding_comment",
    decorator_node_type="annotation",
    container_node_types=["class_declaration", "object_declaration"],
    constant_patterns=["property_declaration"],
    type_patterns=["class_declaration", "object_declaration"],
    call_node_types=["call_expression"],
    import_node_types=["import_header"],
    inheritance_fields=["delegation_specifiers"],
)


# Language registry
LANGUAGE_REGISTRY = {
    "python": PYTHON_SPEC,
    "javascript": JAVASCRIPT_SPEC,
    "typescript": TYPESCRIPT_SPEC,
    "go": GO_SPEC,
    "rust": RUST_SPEC,
    "java": JAVA_SPEC,
    "php": PHP_SPEC,
    "c": C_SPEC,
    "cpp": CPP_SPEC,
    "c_sharp": CSHARP_SPEC,
    "ruby": RUBY_SPEC,
    "swift": SWIFT_SPEC,
    "kotlin": KOTLIN_SPEC,
}
