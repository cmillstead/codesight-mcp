"""Get import relationships for a file."""

from typing import Optional

from ..core.boundaries import make_meta, wrap_untrusted_content
from ..core.errors import sanitize_error, RepoNotFoundError
from ..core.validation import ValidationError
from ..parser.graph import CodeGraph
from ..storage import IndexStore
from ._common import parse_repo, timed, elapsed_ms


_VALID_DIRECTIONS = {"imports", "importers"}


def get_imports(
    repo: str,
    file: str,
    direction: str = "imports",
    storage_path: Optional[str] = None,
) -> dict:
    """Get import relationships for a file.

    Args:
        repo: Repository identifier (owner/repo or just repo name).
        file: Path to file within the repository.
        direction: "imports" (what this file imports) or "importers" (what imports this file).
        storage_path: Custom storage path.

    Returns:
        Dict with import list and _meta envelope.
    """
    start = timed()

    # --- security gate: validate direction allowlist ---
    if direction not in _VALID_DIRECTIONS:
        return {
            "error": f"Invalid direction: {direction!r}. Must be one of: {sorted(_VALID_DIRECTIONS)}",
            "results": [],
        }

    # --- security gate: parse + validate repo identifier ---
    try:
        owner, name = parse_repo(repo, storage_path)
    except RepoNotFoundError as exc:
        return {"error": str(exc)}

    store = IndexStore(base_path=storage_path)
    index = store.load_index(owner, name)

    if not index:
        return {"error": f"Repository not indexed: {owner}/{name}"}

    # --- security gate: validate file is tracked by the index ---
    if file not in index.source_files:
        raise ValidationError("File not found in index")

    # Build graph from index
    graph = CodeGraph.build(index.symbols)

    if direction == "imports":
        # What does this file import?
        import_names = graph.get_imports_of(file)

        # Resolve import names to indexed files where possible
        results: list[dict] = []
        for imp in import_names:
            # Try to find matching source files
            matched_files = []
            for src_file in index.source_files:
                # Match by module name (e.g., "utils" matches "src/utils.py")
                base = src_file.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                if imp == base or imp == src_file or src_file.endswith(f"/{imp}") or src_file.endswith(f"/{imp}.py"):
                    matched_files.append(src_file)

            entry: dict = {
                "import_name": wrap_untrusted_content(imp),
            }
            if matched_files:
                entry["resolved_files"] = [wrap_untrusted_content(f) for f in matched_files]
            results.append(entry)

    else:
        # What files import this file?
        # Derive importable names for the target file
        file_base = file.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        file_module = file.rsplit(".", 1)[0]  # e.g., "src/utils" from "src/utils.py"
        target_names = {file, file_base, file_module}

        # Use graph.get_importers for each possible name form
        importer_files: set[str] = set()
        importer_map: dict[str, str] = {}  # file -> import_name that matched
        for target_name in target_names:
            for importer_file in graph.get_importers(target_name):
                if importer_file != file and importer_file not in importer_files:
                    importer_files.add(importer_file)
                    importer_map[importer_file] = target_name

        results = []
        for imp_file in sorted(importer_files):
            results.append({
                "file": wrap_untrusted_content(imp_file),
                "import_name": wrap_untrusted_content(importer_map[imp_file]),
            })

    ms = elapsed_ms(start)

    return {
        "repo": f"{owner}/{name}",
        "file": wrap_untrusted_content(file),
        "direction": direction,
        "result_count": len(results),
        "results": results,
        "_meta": {
            **make_meta(source="code_index", trusted=False),
            "timing_ms": ms,
        },
    }
