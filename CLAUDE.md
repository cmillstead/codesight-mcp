# CLAUDE.md

## Code Navigation — MANDATORY

**DO NOT use Grep to search this codebase. DO NOT use Bash grep, rg, or find.**
**DO NOT use the Agent tool's Explore subagent for code search.**

This repo is indexed in codesight-mcp. You MUST use codesight via its single dispatch tool for ALL search. The tool is `mcp__codesight__query`. It takes two arguments:
- `operation` — a kebab-case operation name
- `params` — the operation's parameter object (camelCase keys)

Example call:
```
mcp__codesight__query({operation: "search-text", params: {repo: "codesight-mcp", query: "def index_repo", maxResults: 10}})
```

Use `Read` for reading files (code or config). Use codesight operations for *finding* things.

### Indexing
- `index-repo` — index a local or GitHub repository
- `index-folder` — index a specific folder within a repo
- `list-repos` — list all indexed repositories
- `invalidate-cache` — delete index and cached files for a repo

### Navigation
- `get-repo-outline` — directory structure and language breakdown
- `get-file-tree` — detailed file listing with symbol counts
- `get-file-outline` — all symbols in a file with signatures
- `get-symbol` — full source of a specific symbol by ID
- `get-symbols` — batch retrieve multiple symbols by ID
- `get-symbol-context` — symbol + siblings + parent in one call; pass `include_graph=true` for callers/callees/hierarchy too
- `get-key-symbols` — rank symbols by structural importance using PageRank on the call graph

### Search
- `search-symbols` — find functions, classes, methods by name, signature, or summary
- `search-text` — full-text search across all files (returns file, line number, and matched text)
- `search-references` — text search enriched with enclosing symbol context (function/class each hit is in)

### Code Graph
- `get-callers` — find all callers of a symbol
- `get-callees` — find all symbols called by a symbol
- `get-call-chain` — trace call paths between two symbols
- `get-type-hierarchy` — show inheritance chains for a class
- `get-imports` — show import relationships for a symbol
- `get-impact` — analyze impact of changing a symbol (callers + inheritors + importers)
- `get-diagram` — generate Mermaid diagrams from the code graph

### Dependencies & Diffing
- `get-dependencies` — external vs internal import analysis across the repo
- `compare-symbols` — symbol-level diff between two indexed versions (by content hash)
- `get-changes` — git diff → affected symbols → optional impact analysis

### Security & Quality
- `scan-security` — scan symbols for dangerous API usage patterns (OWASP/CWE rules)
- `analyze-complexity` — cyclomatic complexity, cognitive complexity, nesting depth, risk scores
- `get-dead-code` — find unreferenced symbols with zero callers or importers
- `trace-taint` — forward BFS source-to-sink taint analysis via code graph
- `check-licenses` — analyze dependency licenses from lockfiles and flag risks
- `generate-sbom` — generate Software Bill of Materials (CycloneDX, SPDX, or internal JSON)
- `lint-index` — audit index quality: missing fields, orphaned symbols, stale data
- `verify` — verify index integrity: checksums, symbol consistency, file existence

### Usage Stats
- `get-status` — server status: storage configuration, index stats, and feature flags
- `get-usage-stats` — per-operation call counts, error rates, avg response times, and uncalled operations

Use `Read` only when you need content that isn't a named symbol (e.g. config files, pyproject.toml).

## Running Tests

Always use the project venv to run tests:

```bash
.venv/bin/pytest --tb=short -q
```

Do NOT use bare `pytest` or `python -m pytest` — the package must be installed in the venv for imports to resolve.

## Dependencies

After changing dependencies in `pyproject.toml`, always regenerate the lockfile:

```bash
uv lock
```

CI uses `uv sync --frozen` which only installs what's in `uv.lock` — if the lockfile is stale, CI will fail.

## Vault

Project notes: `~/Documents/obsidian-vault/AI/context/goals/projects/codesight-mcp/`
