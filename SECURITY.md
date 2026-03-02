# Security Model

## Threat Model

ironmunch is an MCP server -- it runs locally and exposes tools to a connected AI model. **The connected AI is the attacker.** It can call any tool with any arguments, and it processes untrusted source code that may contain adversarial content designed to manipulate its behavior.

The threat model assumes:

- The AI will attempt path traversal via tool arguments
- The AI will attempt path traversal via poisoned index data
- Source code may contain instructions aimed at the AI (indirect prompt injection)
- Error messages may leak filesystem structure
- Symlinks in indexed directories may point outside the expected root

## Defense Matrix

| Threat | Defense |
|--------|---------|
| Path traversal via tool arguments | 6-step validation chain on every path input |
| Path traversal via poisoned index | Validate file paths from index at retrieval time, not just at index time |
| Symlink escape | 3-layer defense: lstat-based filtering during discovery, parent chain walk during validation, `follow_symlinks=False` default |
| Repository identifier injection | Allowlist pattern (`[a-zA-Z0-9._-]`) with length cap; slashes normalized to `__` |
| Resource exhaustion | Bounded limits on file size, file count, path length, directory depth, search results, and index size |
| Information leakage | Error sanitization: ValidationError messages are pre-approved safe strings, known errnos map to safe messages, unknown errors return a generic fallback, system paths are stripped |
| Indirect prompt injection | Content boundary markers with cryptographic random tokens (Microsoft spotlighting); tool-level untrusted-content warnings in descriptions |
| Secret exposure | Pattern detection during file discovery: files matching secret patterns (`.env`, `*_key`, `*.pem`, etc.) are excluded from indexing |
| Binary confusion | Dual-stage detection: extension-based filtering plus null-byte content sniffing |

## Validation Chain

Every file access runs through a 6-step validation chain (`core/validation.py`):

1. **Null byte rejection** -- Reject paths containing `\x00` (path truncation attacks)
2. **Segment safety** -- Reject `..` traversal and dot-prefixed segments (hidden files)
3. **Length and depth limits** -- Max 512 characters, max 10 directory levels
4. **Path resolution** -- `Path.resolve()` to canonical absolute form
5. **Containment check** -- Resolved path must start with `root + os.sep` (strict prefix)
6. **Symlink parent walk** -- `lstat` every parent directory from file up to root; reject any symlinks

Steps 1-3 run on the raw input (before resolution). Steps 4-6 run on the resolved path. This ordering prevents TOCTOU races where resolution could change what steps 1-3 validated.

## Resource Limits

All limits are defined in `core/limits.py` and enforced server-side:

| Limit | Value | Purpose |
|-------|-------|---------|
| `MAX_FILE_SIZE` | 500 KB | Prevent memory exhaustion from large files |
| `MAX_FILE_COUNT` | 500 | Cap files per index |
| `MAX_PATH_LENGTH` | 512 chars | Prevent buffer-related issues |
| `MAX_DIRECTORY_DEPTH` | 10 levels | Prevent deeply nested traversal |
| `MAX_CONTEXT_LINES` | 100 lines | Cap context around symbol retrieval |
| `MAX_SEARCH_RESULTS` | 50 results | Bound search output size |
| `MAX_INDEX_SIZE` | 50 MB | Cap stored index JSON |
| `GITHUB_API_TIMEOUT` | 30 seconds | Prevent hanging on GitHub requests |

## Content Boundaries

Source code returned by tools is wrapped in boundary markers with cryptographically random tokens:

```
<<<UNTRUSTED_CODE_a1b2c3d4e5f6...>>>
(source code here)
<<<END_UNTRUSTED_CODE_a1b2c3d4e5f6...>>>
```

Each response uses a fresh 32-character hex token (128 bits of entropy), making it computationally infeasible for content to forge a matching end marker. This is based on Microsoft's spotlighting research, which reduced successful prompt injection from >50% to <2%.

Tools that return source code also include `_meta` envelopes marking content as untrusted, and their tool descriptions carry explicit warnings.

## Testing

The adversarial security test suite (`tests/test_adversarial.py`) contains 49 tests covering:

- Null byte injection in paths
- `../` traversal in direct arguments
- `../` traversal via poisoned index entries
- Symlink escape (file symlinks, directory symlinks, parent chain symlinks)
- Unicode normalization attacks
- Double-encoding attacks
- Oversized paths and deeply nested paths
- Repository identifier injection (slashes, dots, shell metacharacters)
- Error message sanitization (no path leakage)
- Content boundary marker integrity
- Resource limit enforcement
- Secret file detection
- Binary file detection
- Combined attack vectors

All tests use real temporary directories and real filesystem operations. No mocking of security-critical code paths.

## Issues Fixed from jcodemunch-mcp

Four security issues were identified in the original jcodemunch-mcp and addressed in ironmunch:

1. **Unvalidated file reads at retrieval time** -- jcodemunch validated paths only during indexing. If an index file was modified (or crafted) after indexing, `get_symbol` and `search_text` would read arbitrary files. ironmunch validates every file path from the index at retrieval time via `validate_file_access()`.

2. **Unbounded `context_lines` parameter** -- `get_symbol` accepted an arbitrary `context_lines` value, allowing the AI to request the entire file (defeating the purpose of symbol-level retrieval). ironmunch clamps `context_lines` to `MAX_CONTEXT_LINES` (100).

3. **Raw error messages exposed to AI** -- Exceptions were returned as-is, potentially leaking filesystem paths, usernames, and internal structure. ironmunch sanitizes all errors through `sanitize_error()`, which passes through only pre-approved ValidationError messages or known errno mappings.

4. **No content boundary markers** -- Source code was returned as plain text with no indication that it was untrusted. ironmunch wraps all source code in cryptographic boundary markers and includes `_meta` trust envelopes.
