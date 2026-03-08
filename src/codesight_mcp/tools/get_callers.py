"""Get callers of a symbol -- reverse call graph traversal."""

from collections import deque
from typing import Optional

from ..core.boundaries import make_meta, wrap_untrusted_content
from ..core.errors import sanitize_error, RepoNotFoundError
from ..parser.graph import CodeGraph
from ..storage import IndexStore
from ._common import parse_repo, timed, elapsed_ms


def get_callers(
    repo: str,
    symbol_id: str,
    max_depth: int = 1,
    storage_path: Optional[str] = None,
) -> dict:
    """Get symbols that call the specified symbol.

    Args:
        repo: Repository identifier (owner/repo or just repo name).
        symbol_id: Symbol ID to find callers of.
        max_depth: Maximum traversal depth (1 = direct callers only, max 5).
        storage_path: Custom storage path.

    Returns:
        Dict with caller list and _meta envelope.
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

    # Clamp max_depth
    max_depth = min(max(max_depth, 1), 5)

    # Build graph from index
    graph = CodeGraph.build(index.symbols)

    # BFS over graph.get_callers() for transitive lookup
    visited: set[str] = set()
    callers: list[dict] = []
    queue: deque[tuple[str, int]] = deque()
    queue.append((symbol_id, 1))

    while queue:
        current_id, depth = queue.popleft()
        if depth > max_depth:
            continue

        for caller_id in graph.get_callers(current_id):
            if caller_id in visited or caller_id == symbol_id:
                continue
            visited.add(caller_id)
            sym = graph._symbols_by_id.get(caller_id, {})
            callers.append({
                "id": wrap_untrusted_content(caller_id),
                "name": wrap_untrusted_content(sym.get("name", "")),
                "kind": sym.get("kind", ""),
                "file": wrap_untrusted_content(sym.get("file", "")),
                "line": sym.get("line", 0),
                "depth": depth,
            })
            if depth < max_depth:
                queue.append((caller_id, depth + 1))

    ms = elapsed_ms(start)

    target_name = target.get("name", "")

    return {
        "repo": f"{owner}/{name}",
        "symbol_id": wrap_untrusted_content(symbol_id),
        "symbol_name": wrap_untrusted_content(target_name),
        "max_depth": max_depth,
        "caller_count": len(callers),
        "callers": callers,
        "_meta": {
            **make_meta(source="code_index", trusted=False),
            "timing_ms": ms,
        },
    }
