"""Get a symbol plus its structural neighborhood.

Returns the target symbol (with source), its siblings (other symbols in the same
scope), and its parent (if any). Replaces the common get_symbol → get_file_outline
→ Read multi-tool pattern with a single call.
"""

from typing import Optional

from ..security import sanitize_signature_for_api
from ..core.boundaries import wrap_untrusted_content, make_meta
from ..core.errors import sanitize_error
from ._common import RepoContext, timed, elapsed_ms
from .registry import ToolSpec, register


def _sym_summary(sym: dict) -> dict:
    """Return a lightweight summary dict for a symbol (no source)."""
    return {
        "id": wrap_untrusted_content(sym["id"]),
        "kind": sym["kind"],
        "name": wrap_untrusted_content(sym["name"]),
        "signature": wrap_untrusted_content(sym.get("signature", "")),
        "line": sym.get("line", 0),
        "end_line": sym.get("end_line", 0),
        "summary": wrap_untrusted_content(sym.get("summary", "")),
    }


def get_context(
    repo: str,
    symbol_id: str,
    storage_path: Optional[str] = None,
) -> dict:
    """Get a symbol plus its structural neighborhood.

    Given a symbol_id, returns:
    - The target symbol with full source code.
    - Its siblings: other symbols in the same file with the same parent scope.
      For methods this is other methods of the same class; for module-level
      symbols this is other module-level symbols in the same file.
    - Its parent symbol (signature only), or None for module-level symbols.

    The target symbol does NOT appear in its own siblings list.
    Symbols from other files are never returned as siblings.

    Args:
        repo: Repository identifier (owner/repo or just repo name).
        symbol_id: Symbol ID from get_file_outline or search_symbols.
        storage_path: Custom storage path.

    Returns:
        Dict with symbol, siblings, parent, and _meta envelope.
    """
    start = timed()

    ctx = RepoContext.resolve(repo, storage_path)
    if isinstance(ctx, dict):
        return ctx
    owner, name, store, index = ctx.owner, ctx.name, ctx.store, ctx.index

    # Look up the target symbol
    symbol = index.get_symbol(symbol_id)
    if not symbol:
        return {"error": f"Symbol not found: {symbol_id}"}

    # Retrieve source code for the target symbol
    try:
        source = store.get_symbol_content(owner, name, symbol_id, index=index)
    except Exception as exc:
        return {"error": sanitize_error(exc)}

    target_file = symbol.get("file", "")
    target_parent = symbol.get("parent")  # None for module-level symbols

    # Find siblings: same file, same parent (including None for module-level)
    siblings = []
    for sym in index.symbols:
        # Must be in the same file
        if sym.get("file") != target_file:
            continue
        # Must not be the target itself
        if sym["id"] == symbol_id:
            continue
        # Must have the same parent scope
        if sym.get("parent") != target_parent:
            continue
        siblings.append(_sym_summary(sym))

    # Sort siblings by line number for stable output
    siblings.sort(key=lambda s: s["line"])

    # Find the parent symbol (if any)
    parent = None
    if target_parent:
        parent_sym = index.get_symbol(target_parent)
        if parent_sym:
            parent = _sym_summary(parent_sym)

    ms = elapsed_ms(start)

    return {
        "symbol": {
            "id": wrap_untrusted_content(symbol["id"]),
            "kind": symbol["kind"],
            "name": wrap_untrusted_content(symbol["name"]),
            "signature": wrap_untrusted_content(symbol.get("signature", "")),
            "line": symbol.get("line", 0),
            "end_line": symbol.get("end_line", 0),
            "summary": wrap_untrusted_content(symbol.get("summary", "")),
            "source": wrap_untrusted_content(sanitize_signature_for_api(source)) if source else "",
        },
        "siblings": siblings,
        "parent": parent,
        "_meta": {
            **make_meta(source="code_index", trusted=False),
            "timing_ms": ms,
            "sibling_count": len(siblings),
        },
    }


_spec = register(ToolSpec(
    name="get_context",
    description=(
        "Get a symbol plus its structural neighborhood: the target symbol "
        "(with source), its siblings in the same scope, and its parent "
        "(signature only). Replaces the common get_symbol → get_file_outline "
        "→ Read multi-tool pattern with a single call."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository identifier (owner/repo or just repo name)",
            },
            "symbol_id": {
                "type": "string",
                "description": "Symbol ID from get_file_outline or search_symbols",
            },
        },
        "required": ["repo", "symbol_id"],
    },
    handler=lambda args, storage_path: get_context(
        repo=args["repo"],
        symbol_id=args["symbol_id"],
        storage_path=storage_path,
    ),
    untrusted=True,
    required_args=["repo", "symbol_id"],
))
