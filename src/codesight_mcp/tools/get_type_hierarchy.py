"""Get type hierarchy -- inheritance tree for a class or type."""

from typing import Optional

from ..core.boundaries import make_meta, wrap_untrusted_content
from ..core.errors import sanitize_error, RepoNotFoundError
from ..parser.graph import CodeGraph
from ..storage import IndexStore
from ._common import parse_repo, timed, elapsed_ms


def get_type_hierarchy(
    repo: str,
    symbol_id: str,
    storage_path: Optional[str] = None,
) -> dict:
    """Get the inheritance hierarchy for a class or type.

    Args:
        repo: Repository identifier (owner/repo or just repo name).
        symbol_id: Symbol ID of the class/type to inspect.
        storage_path: Custom storage path.

    Returns:
        Dict with parents (ancestors) and children (descendants) and _meta envelope.
    """
    start = timed()

    # --- security gate: parse + validate repo identifier ---
    try:
        owner, name = parse_repo(repo, storage_path)
    except RepoNotFoundError as exc:
        return {"error": str(exc)}

    store = IndexStore(base_path=storage_path)
    index = store.load_index(owner, name)

    if not index:
        return {"error": f"Repository not indexed: {owner}/{name}"}

    # Verify target symbol exists
    target = index.get_symbol(symbol_id)
    if not target:
        return {"error": f"Symbol not found: {symbol_id}"}

    target_name = target.get("name", "")

    # Build graph from index
    graph = CodeGraph.build(index.symbols)

    # Use CodeGraph.get_type_hierarchy for O(1) lookups
    hierarchy = graph.get_type_hierarchy(symbol_id)

    # Format parents with symbol details and relationship type
    parents: list[dict] = []
    visited_parents: set[str] = {symbol_id}

    def _collect_parents(sid: str) -> None:
        h = graph.get_type_hierarchy(sid)
        for parent_key in h["parents"]:
            if parent_key in visited_parents:
                continue
            visited_parents.add(parent_key)
            sym = graph._symbols_by_id.get(parent_key)
            if sym:
                parents.append({
                    "id": wrap_untrusted_content(parent_key),
                    "name": wrap_untrusted_content(sym.get("name", "")),
                    "kind": sym.get("kind", ""),
                    "file": wrap_untrusted_content(sym.get("file", "")),
                    "line": sym.get("line", 0),
                    "relationship": "inherits",
                })
                # Recurse to find grandparents
                _collect_parents(parent_key)
            else:
                # Unresolved parent (external type) -- include with name only
                parents.append({
                    "id": wrap_untrusted_content(parent_key),
                    "name": wrap_untrusted_content(parent_key),
                    "kind": "",
                    "file": wrap_untrusted_content(""),
                    "line": 0,
                    "relationship": "inherits",
                })
        for iface_key in h["implements"]:
            if iface_key in visited_parents:
                continue
            visited_parents.add(iface_key)
            sym = graph._symbols_by_id.get(iface_key)
            if sym:
                parents.append({
                    "id": wrap_untrusted_content(iface_key),
                    "name": wrap_untrusted_content(sym.get("name", "")),
                    "kind": sym.get("kind", ""),
                    "file": wrap_untrusted_content(sym.get("file", "")),
                    "line": sym.get("line", 0),
                    "relationship": "implements",
                })
                _collect_parents(iface_key)
            else:
                parents.append({
                    "id": wrap_untrusted_content(iface_key),
                    "name": wrap_untrusted_content(iface_key),
                    "kind": "",
                    "file": wrap_untrusted_content(""),
                    "line": 0,
                    "relationship": "implements",
                })

    _collect_parents(symbol_id)

    # Format children with symbol details and relationship type
    children: list[dict] = []
    visited_children: set[str] = {symbol_id}

    def _collect_children(sid: str) -> None:
        h = graph.get_type_hierarchy(sid)
        for child_key in h["children"]:
            if child_key in visited_children:
                continue
            visited_children.add(child_key)
            sym = graph._symbols_by_id.get(child_key)
            if sym:
                children.append({
                    "id": wrap_untrusted_content(child_key),
                    "name": wrap_untrusted_content(sym.get("name", "")),
                    "kind": sym.get("kind", ""),
                    "file": wrap_untrusted_content(sym.get("file", "")),
                    "line": sym.get("line", 0),
                    "relationship": "inherits",
                })
                _collect_children(child_key)
        for impl_key in h["implemented_by"]:
            if impl_key in visited_children:
                continue
            visited_children.add(impl_key)
            sym = graph._symbols_by_id.get(impl_key)
            if sym:
                children.append({
                    "id": wrap_untrusted_content(impl_key),
                    "name": wrap_untrusted_content(sym.get("name", "")),
                    "kind": sym.get("kind", ""),
                    "file": wrap_untrusted_content(sym.get("file", "")),
                    "line": sym.get("line", 0),
                    "relationship": "implements",
                })
                _collect_children(impl_key)

    _collect_children(symbol_id)

    ms = elapsed_ms(start)

    return {
        "repo": f"{owner}/{name}",
        "symbol_id": wrap_untrusted_content(symbol_id),
        "symbol_name": wrap_untrusted_content(target_name),
        "kind": target.get("kind", ""),
        "parent_count": len(parents),
        "parents": parents,
        "child_count": len(children),
        "children": children,
        "_meta": {
            **make_meta(source="code_index", trusted=False),
            "timing_ms": ms,
        },
    }
