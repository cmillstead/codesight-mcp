"""Test that limit parameters declare machine-readable minimum/maximum bounds."""

from codesight_mcp.tools.registry import load_all_specs
from codesight_mcp.server import _INT_PARAM_BOUNDS


def test_limit_properties_declare_machine_readable_bounds():
    """All tools with limit parameters must declare minimum/maximum matching server bounds."""
    lo, hi = _INT_PARAM_BOUNDS["limit"]
    assert (lo, hi) == (1, 100)
    offenders = []
    for name, spec in load_all_specs().items():
        prop = spec.input_schema.get("properties", {}).get("limit")
        if not prop:
            continue
        if prop.get("minimum") != lo or prop.get("maximum") != hi:
            offenders.append((name, prop.get("minimum"), prop.get("maximum")))
    assert offenders == [], f"limit props must declare minimum={lo}, maximum={hi}: {offenders}"
