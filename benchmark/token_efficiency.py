#!/usr/bin/env python3
"""
codesight-mcp vs jCodeMunch — Token Efficiency Benchmark

Indexes a target codebase with each tool (into a temp dir), runs a set of
representative queries, and compares how many tokens each tool uses to answer
versus reading all source files directly.

Token counting: len(text) // 4  (char-based estimate, no tiktoken dependency)
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------
def count_tokens(text: str) -> int:
    """Estimate tokens using char/4 heuristic."""
    return len(text) // 4


# ---------------------------------------------------------------------------
# Spotlighting wrapper stripper (codesight-mcp only)
# ---------------------------------------------------------------------------
_WRAPPER = re.compile(
    r"<<<UNTRUSTED_CODE_[0-9a-f]+>>>(.*?)<<<END_UNTRUSTED_CODE_[0-9a-f]+>>>",
    re.DOTALL,
)


def unwrap(s: str) -> str:
    """Strip codesight-mcp spotlighting boundary markers from a string."""
    m = _WRAPPER.search(s)
    return m.group(1).strip() if m else s


# ---------------------------------------------------------------------------
# Source extensions and baseline measurement
# ---------------------------------------------------------------------------
SOURCE_EXTENSIONS = {".py", ".rs", ".go", ".ts", ".js", ".java", ".cs"}
SKIP_DIRS = {"_storage", ".venv", "__pycache__", ".git", "node_modules", ".mypy_cache"}


def count_baseline_tokens(target: Path) -> tuple[int, int, int]:
    """Return (token_count, file_count, loc) for all source files under target."""
    tokens = 0
    files = 0
    loc = 0
    for root, dirs, filenames in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in filenames:
            if Path(fname).suffix in SOURCE_EXTENSIONS:
                fpath = Path(root) / fname
                try:
                    text = fpath.read_text(errors="replace")
                    tokens += count_tokens(text)
                    files += 1
                    loc += text.count("\n")
                except OSError:
                    pass
    return tokens, files, loc


# ---------------------------------------------------------------------------
# codesight-mcp imports
# ---------------------------------------------------------------------------
try:
    from codesight_mcp.tools.index_folder import index_folder as im_index_folder
    from codesight_mcp.tools.search_symbols import search_symbols as im_search
    from codesight_mcp.tools.get_symbol import get_symbols as im_get_symbols

    IRONMUNCH_AVAILABLE = True
except ImportError:
    IRONMUNCH_AVAILABLE = False

# ---------------------------------------------------------------------------
# jCodeMunch imports (optional)
# ---------------------------------------------------------------------------
try:
    from jcodemunch_mcp.tools.search_symbols import search_symbols as jcm_search
    from jcodemunch_mcp.tools.get_symbol import get_symbols as jcm_get_symbols
    from jcodemunch_mcp.tools.index_folder import index_folder as jcm_index_folder

    JCODEMUNCH_AVAILABLE = True
except ImportError:
    JCODEMUNCH_AVAILABLE = False


# ---------------------------------------------------------------------------
# Default queries
# ---------------------------------------------------------------------------
QUERIES = [
    "How does path validation work?",
    "How are secrets detected and redacted?",
    "How does the batch summarizer work?",
    "How are symbols indexed from source files?",
    "How is rate limiting implemented?",
    "How are symbols searched and scored?",
    "How does atomic index write work?",
    "How are file paths validated for traversal?",
]


# ---------------------------------------------------------------------------
# Benchmark helpers
# ---------------------------------------------------------------------------
def _supports_param(fn, param: str) -> bool:
    try:
        return param in inspect.signature(fn).parameters
    except (ValueError, TypeError):
        return False


def run_codesight_mcp(target: Path, queries: list[str], top_k: int) -> list[int]:
    """Index target with codesight-mcp, run queries, return token counts per query."""
    if not IRONMUNCH_AVAILABLE:
        raise RuntimeError("codesight-mcp not importable")

    with tempfile.TemporaryDirectory(prefix="im_bench_") as tmp:
        kwargs: dict = dict(
            path=str(target),
            use_ai_summaries=False,
            storage_path=tmp,
        )
        if _supports_param(im_index_folder, "allowed_roots"):
            kwargs["allowed_roots"] = [str(target.resolve().parent)]

        idx = im_index_folder(**kwargs)
        repo = idx["repo"]

        token_counts = []
        for query in queries:
            sr = im_search(repo=repo, query=query, max_results=5, storage_path=tmp)
            results = sr.get("results", [])
            raw_ids = [r.get("id", "") for r in results[:top_k]]
            ids = [unwrap(rid) for rid in raw_ids]

            gs = im_get_symbols(repo=repo, symbol_ids=ids, storage_path=tmp)
            response_text = json.dumps(gs)
            token_counts.append(count_tokens(response_text))

        return token_counts


def run_jcodemunch(target: Path, queries: list[str], top_k: int) -> list[int]:
    """Index target with jCodeMunch, run queries, return token counts per query."""
    if not JCODEMUNCH_AVAILABLE:
        raise RuntimeError("jCodeMunch not importable")

    with tempfile.TemporaryDirectory(prefix="jcm_bench_") as tmp:
        kwargs: dict = dict(
            path=str(target),
            use_ai_summaries=False,
            storage_path=tmp,
        )
        idx = jcm_index_folder(**kwargs)
        repo = idx.get("repo", "")

        token_counts = []
        for query in queries:
            sr = jcm_search(repo=repo, query=query, max_results=5, storage_path=tmp)
            results = sr.get("results", [])
            ids = [r.get("id", "") for r in results[:top_k]]

            gs = jcm_get_symbols(repo=repo, symbol_ids=ids, storage_path=tmp)
            response_text = json.dumps(gs)
            token_counts.append(count_tokens(response_text))

        return token_counts


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def reduction_pct(baseline: int, retrieved: int) -> str:
    if baseline == 0:
        return "N/A"
    pct = (1 - retrieved / baseline) * 100
    return f"{pct:.1f}%"


def multiplier(baseline: int, retrieved: int) -> str:
    if retrieved == 0:
        return "N/A"
    return f"~{baseline // retrieved}x"


def print_table(
    queries: list[str],
    baseline: int,
    im_counts: Optional[list[int]],
    jcm_counts: Optional[list[int]],
    target: Path,
    file_count: int,
    loc: int,
    top_k: int = 3,
) -> None:
    q_width = max(len(q) for q in queries) + 2
    col_w = 12

    header_parts = [f"{'Query':<{q_width}}"]
    sep_parts = ["-" * q_width]
    if im_counts is not None:
        header_parts.append(f"{'codesight-mcp':>{col_w}}")
        sep_parts.append("-" * col_w)
    if jcm_counts is not None:
        header_parts.append(f"{'jCodeMunch':>{col_w}}")
        sep_parts.append("-" * col_w)
    header_parts.append(f"{'Baseline':>{col_w}}")
    sep_parts.append("-" * col_w)

    print()
    print("codesight-mcp vs jCodeMunch — Token Efficiency Benchmark")
    print("=" * 57)
    print(f"Target:      {target}  ({file_count} files, {loc:,} LOC)")
    print(f"Baseline:    ~{baseline:,} tokens (char/4 estimate, reading all source files)")
    print("Tokenizer:   char/4 estimate")
    print(f"Top-K:       {top_k} symbols retrieved per query")
    print()

    print("  ".join(header_parts))
    print("  ".join(sep_parts))

    for i, q in enumerate(queries):
        row = [f"{q:<{q_width}}"]
        if im_counts is not None:
            row.append(f"{im_counts[i]:>{col_w},}")
        if jcm_counts is not None:
            row.append(f"{jcm_counts[i]:>{col_w},}")
        row.append(f"{baseline:>{col_w},}")
        print("  ".join(row))

    print("  ".join(sep_parts))

    avg_row = [f"{'Average':<{q_width}}"]
    if im_counts is not None:
        avg_im = sum(im_counts) // len(im_counts)
        avg_row.append(f"{avg_im:>{col_w},}")
    if jcm_counts is not None:
        avg_jcm = sum(jcm_counts) // len(jcm_counts)
        avg_row.append(f"{avg_jcm:>{col_w},}")
    avg_row.append(f"{baseline:>{col_w},}")
    print("  ".join(avg_row))
    print()

    print("Reduction vs baseline:")
    if im_counts is not None:
        avg_im = sum(im_counts) // len(im_counts)
        print(f"  codesight-mcp:  {reduction_pct(baseline, avg_im)}  ({multiplier(baseline, avg_im)} fewer tokens)")
    if jcm_counts is not None:
        avg_jcm = sum(jcm_counts) // len(jcm_counts)
        print(f"  jCodeMunch: {reduction_pct(baseline, avg_jcm)}  ({multiplier(baseline, avg_jcm)} fewer tokens)")

    if im_counts is not None and jcm_counts is not None:
        avg_im = sum(im_counts) // len(im_counts)
        avg_jcm = sum(jcm_counts) // len(jcm_counts)
        overhead = avg_im - avg_jcm
        print()
        print(f"Token overhead from codesight-mcp security features (spotlighting): +{overhead:,} tokens avg per query")
        print("Note: codesight-mcp wraps all untrusted fields in boundary markers for prompt injection defense.")
        print("      jCodeMunch does not apply spotlighting. This accounts for the difference.")

    print()
    print("Published benchmark (jCodeMunch, .NET 10 codebase, 1 query): 99.7% reduction")
    print("Note: Different codebase and single-query methodology; not directly comparable.")


def print_json(
    queries: list[str],
    baseline: int,
    im_counts: Optional[list[int]],
    jcm_counts: Optional[list[int]],
    target: Path,
    file_count: int,
    loc: int,
    top_k: int,
) -> None:
    avg_im = sum(im_counts) // len(im_counts) if im_counts else None
    avg_jcm = sum(jcm_counts) // len(jcm_counts) if jcm_counts else None

    output = {
        "target": str(target),
        "file_count": file_count,
        "loc": loc,
        "baseline_tokens": baseline,
        "tokenizer": "char/4",
        "top_k": top_k,
        "queries": [
            {
                "query": q,
                "codesight_mcp_tokens": im_counts[i] if im_counts else None,
                "jcodemunch_tokens": jcm_counts[i] if jcm_counts else None,
                "baseline_tokens": baseline,
            }
            for i, q in enumerate(queries)
        ],
        "averages": {
            "codesight-mcp": avg_im,
            "jcodemunch": avg_jcm,
            "baseline": baseline,
        },
        "reduction_pct": {
            "codesight-mcp": round((1 - avg_im / baseline) * 100, 1) if avg_im and baseline else None,
            "jcodemunch": round((1 - avg_jcm / baseline) * 100, 1) if avg_jcm and baseline else None,
        },
    }
    print(json.dumps(output, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Token efficiency benchmark: codesight-mcp vs jCodeMunch"
    )
    parser.add_argument(
        "--target",
        default=str(Path(__file__).parent.parent / "src" / "codesight-mcp"),
        help="Path to codebase to index (default: src/codesight_mcp/)",
    )
    parser.add_argument(
        "--tool",
        choices=["codesight-mcp", "jcodemunch", "both"],
        default="both",
        help="Which tool(s) to benchmark (default: both)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of symbols to retrieve per query (default: 3)",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )
    args = parser.parse_args()

    target = Path(args.target).resolve()
    if not target.exists():
        print(f"Error: target path does not exist: {target}", file=sys.stderr)
        sys.exit(1)

    run_im = args.tool in ("codesight-mcp", "both")
    run_jcm = args.tool in ("jcodemunch", "both")

    if run_im and not IRONMUNCH_AVAILABLE:
        print("Error: codesight-mcp is not installed/importable.", file=sys.stderr)
        sys.exit(1)

    if run_jcm and not JCODEMUNCH_AVAILABLE:
        print(
            "jCodeMunch is not installed. Install with:\n"
            "  pip install git+https://github.com/jgravelle/jcodemunch-mcp.git",
            file=sys.stderr,
        )
        if args.tool == "jcodemunch":
            sys.exit(1)
        print("Falling back to codesight-mcp-only mode.\n", file=sys.stderr)
        run_jcm = False

    print(f"Measuring baseline (reading all source files under {target})...", file=sys.stderr)
    baseline, file_count, loc = count_baseline_tokens(target)

    im_counts: Optional[list[int]] = None
    jcm_counts: Optional[list[int]] = None

    if run_im:
        print("Indexing with codesight-mcp and running queries...", file=sys.stderr)
        im_counts = run_codesight_mcp(target, QUERIES, args.top_k)

    if run_jcm:
        print("Indexing with jCodeMunch and running queries...", file=sys.stderr)
        jcm_counts = run_jcodemunch(target, QUERIES, args.top_k)

    if args.format == "json":
        print_json(QUERIES, baseline, im_counts, jcm_counts, target, file_count, loc, args.top_k)
    else:
        print_table(QUERIES, baseline, im_counts, jcm_counts, target, file_count, loc, args.top_k)


if __name__ == "__main__":
    main()
