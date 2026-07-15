"""Tests for the canonical registry bootstrap (load_all_specs).

load_all_specs() must be the single side-effect-free entry point that
populates the tool registry, without requiring an import of server.py.
"""

from codesight_mcp.tools.registry import load_all_specs, get_all_specs


def test_load_all_specs_idempotent_same_set():
    first = load_all_specs()
    second = load_all_specs()
    assert set(first) == set(second)
    assert len(first) == 34
    assert first.keys() == get_all_specs().keys()


def test_required_args_agree_with_input_schema():
    for name, spec in load_all_specs().items():
        schema_required = set(spec.input_schema.get("required", []))
        assert set(spec.required_args or []) == schema_required, name
