"""Get callees of a symbol -- forward call graph traversal."""

from collections import deque
from typing import Optional

from ..core.boundaries import make_meta, wrap_untrusted_content
from ..core.errors import sanitize_error, RepoNotFoundError
from ..parser.graph import CodeGraph
from ..storage import IndexStore
from ._common import parse_repo, timed, elapsed_ms


def get_callees(
    repo: str,
    symbol_id: str,
    max_depth: int = 1,
    storage_path: Optional[str] = None,
) -> dict:
    """Get symbols that the specified symbol calls.

    Args:
        repo: Repository identifier (owner/repo or just repo name).
        symbol_id: Symbol ID to find callees of.
        max_depth: Maximum traversal depth (1 = direct callees only, max 5).
        storage_path: Custom storage path.

    Returns:
        Dict with callee list and _meta envelope.
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

    # BFS over graph.get_callees() for transitive lookup
    visited: set[str] = {symbol_id}
    callees: list[dict] = []
    queue: deque[tuple[str, int]] = deque()
    queue.append((symbol_id, 1))

    while queue:
        current_id, depth = queue.popleft()
        if depth > max_depth:
            continue

        for callee_id in graph.get_callees(current_id):
            if callee_id in visited:
                continue
            visited.add(callee_id)
            sym = graph._symbols_by_id.get(callee_id, {})
            callees.append({
                "id": wrap_untrusted_content(callee_id),
                "name": wrap_untrusted_content(sym.get("name", "")),
                "kind": sym.get("kind", ""),
                "file": wrap_untrusted_content(sym.get("file", "")),
                "line": sym.get("line", 0),
                "depth": depth,
            })
            if depth < max_depth:
                queue.append((callee_id, depth + 1))

    ms = elapsed_ms(start)

    target_name = target.get("name", "")

    return {
        "repo": f"{owner}/{name}",
        "symbol_id": wrap_untrusted_content(symbol_id),
        "symbol_name": wrap_untrusted_content(target_name),
        "max_depth": max_depth,
        "callee_count": len(callees),
        "callees": callees,
        "_meta": {
            **make_meta(source="code_index", trusted=False),
            "timing_ms": ms,
        },
    }
