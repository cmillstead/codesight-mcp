"""Declarative tool registry -- each tool file exports a ToolSpec."""

from dataclasses import dataclass, field
from typing import Any, Callable

from mcp.types import ToolAnnotations


@dataclass
class ToolSpec:
    """Everything server.py needs to register and dispatch a tool."""

    name: str
    description: str
    input_schema: dict
    handler: Callable[..., Any]
    untrusted: bool = False
    index_gate: bool = False
    destructive: bool = False
    required_args: list[str] = field(default_factory=list)
    annotations: ToolAnnotations | None = None
    ci_exit_key: str | None = None


_REGISTRY: dict[str, ToolSpec] = {}


def register(spec: ToolSpec) -> ToolSpec:
    """Register a tool spec. Raises ValueError on duplicate name."""
    if spec.name in _REGISTRY:
        raise ValueError(f"Duplicate tool registration: {spec.name}")
    _REGISTRY[spec.name] = spec
    return spec


def get_all_specs() -> dict[str, ToolSpec]:
    """Return a copy of the registry."""
    return dict(_REGISTRY)


def load_all_specs() -> dict[str, ToolSpec]:
    """Import every tool module (populating the registry via side-effects),
    then return all specs. Idempotent -- safe to call repeatedly. The
    canonical tool-import list; scripts/tests use this instead of importing
    server.py.
    """
    from . import (  # noqa: F401
        index_repo, index_folder, list_repos, get_file_tree, get_file_outline,
        get_symbol, search_symbols, search_text, invalidate_cache, get_repo_outline,
        get_callers, get_callees, get_call_chain, get_type_hierarchy, get_imports,
        get_impact, get_dead_code, get_status, analyze_complexity, get_key_symbols,
        get_diagram, get_symbol_context, search_references, get_dependencies,
        compare_symbols, get_changes, get_usage_stats, verify, lint_index,
        generate_sbom, check_licenses, scan_security, trace_taint,
    )
    return get_all_specs()


def _snapshot_registry() -> dict[str, ToolSpec]:
    """Snapshot the registry state. For testing only."""
    return dict(_REGISTRY)


def _restore_registry(snapshot: dict[str, ToolSpec]) -> None:
    """Restore the registry to a previous snapshot. For testing only."""
    _REGISTRY.clear()
    _REGISTRY.update(snapshot)
