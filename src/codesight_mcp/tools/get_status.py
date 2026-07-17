"""Health-check / status tool."""

import os
from typing import Optional

from ..core.boundaries import make_meta
from ..core.freshness import INDEX_AGE_THRESHOLD_DAYS
from ..security import _NO_REDACT
from ..storage import INDEX_VERSION
from ._common import timed, elapsed_ms, _get_shared_store
from mcp.types import ToolAnnotations
from .registry import ToolSpec, register


def get_status(storage_path: Optional[str] = None) -> dict:
    """Return a quick health-check snapshot.

    Returns:
        Dict with storage_configured, repo_count, total_symbols,
        version, and _meta envelope.
    """
    start = timed()
    store = _get_shared_store(storage_path)
    repos = store.list_repos()

    total_symbols = sum(r.get("symbol_count", 0) for r in repos)
    ms = elapsed_ms(start)

    # ADV-LOW-7: Removed has_api_key — leaks API key presence to MCP clients.
    # ADV-LOW-13: Redact storage_path — absolute path leaks directory structure.
    result = {
        "storage_configured": storage_path is not None or bool(os.environ.get("CODE_INDEX_PATH")),
        "repo_count": len(repos),
        "total_symbols": total_symbols,
        "version": INDEX_VERSION,
        "_meta": {
            **make_meta(source="status", trusted=True),
            "timing_ms": ms,
        },
    }

    # Staleness surface — aggregate counts only, no repo-name strings
    # (get_status is a trusted envelope).
    aged = sum(1 for r in repos if r.get("age_threshold_exceeded") is True)
    # UNKNOWN age (unparseable or meaningfully-future indexed_at) must never be
    # silently treated as fresh -- fail closed by surfacing it as its own bucket.
    unknown = sum(
        1 for r in repos
        if "age_threshold_exceeded" in r and r["age_threshold_exceeded"] is None
    )
    known = [r["index_age_days"] for r in repos if r.get("index_age_days") is not None]
    result["aged_repo_count"] = aged
    result["unknown_age_repo_count"] = unknown
    if known:
        result["oldest_index_age_days"] = max(known)
    if aged or unknown:
        parts = []
        if aged:
            parts.append(
                f"{aged} indexed repo(s) exceed the {INDEX_AGE_THRESHOLD_DAYS}-day freshness threshold"
            )
        if unknown:
            parts.append(
                f"{unknown} indexed repo(s) have an unparseable-or-future indexed_at timestamp "
                "and are treated as NOT fresh"
            )
        result["staleness_warning"] = (
            "; ".join(parts) + "; re-index with `codesight-mcp index-folder --path <dir>` or "
            "`codesight-mcp index-repo <url>`."
        )

    # ADV-LOW-11: Warn when redaction is disabled
    if _NO_REDACT:
        result["redaction_disabled"] = True

    return result


_spec = register(ToolSpec(
    name="get_status",
    description="Quick health check: storage path, repo count, total symbols, and index version.",
    input_schema={
        "type": "object",
        "properties": {},
    },
    handler=lambda args, storage_path: get_status(storage_path=storage_path),
    required_args=[],
    annotations=ToolAnnotations(title="Get Status", readOnlyHint=True, openWorldHint=False),
))
