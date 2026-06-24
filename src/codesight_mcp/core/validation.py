"""Path validation chain — ported from basalt-mcp.

Every file access flows through validate_path() which runs
the full 6-step chain. Individual assertions are exposed for
targeted use.
"""

import os
import unicodedata
from pathlib import Path

from .limits import MAX_PATH_LENGTH, MAX_DIRECTORY_DEPTH


class ValidationError(Exception):
    """Raised when a path fails validation. Message is safe to return to AI."""
    pass


def assert_no_control_chars(path: str) -> None:
    """Step 1: Reject null bytes, C0 controls, DEL, and C1 controls.

    Rejects:
    - 0x00–0x1F: C0 control characters (includes null byte, tab, newline, etc.)
    - 0x7F: DEL — would break fnmatch pattern matching for secret filenames
    - 0x80–0x9F: C1 control block — can bypass continuous-ASCII regex assumptions
    """
    if not path:
        raise ValidationError("Path must not be empty")
    if any(ord(c) < 32 or ord(c) == 127 or 128 <= ord(c) <= 159 for c in path):
        raise ValidationError("Path contains control character")


# Backwards-compatible alias — used by existing tests and core/__init__.py exports.
assert_no_null_bytes = assert_no_control_chars


# Dot-prefixed directories that are safe for code indexing
_ALLOWED_DOT_PREFIXES = {".github", ".gitlab", ".circleci", ".husky", ".vscode"}


def assert_safe_segments(path: str) -> None:
    """Step 2: Reject dot-prefixed segments and '..' traversal.

    Allows known-safe dot-prefixed directories (.github, etc.).

    The dot-prefixed-segment (hidden-file) check is SKIPPED for absolute paths.
    Absolute paths only reach this function when safe_read_file re-validates an
    already-validated abs_path for defense-in-depth; the relative-path check
    already enforced the hidden-segment policy when the path was first validated.
    The storage root itself (e.g. ~/.code-index/<repo>) contains a hidden segment
    that must not be rejected on re-validation.  The traversal-critical '..'
    rejection remains UNCONDITIONAL regardless of whether the path is absolute.
    """
    is_absolute = Path(path).is_absolute()
    for segment in Path(path).parts:
        if segment == ".":
            continue
        if segment == "..":
            raise ValidationError(f"Path contains unsafe segment: {segment}")
        if (
            not is_absolute
            and segment.startswith(".")
            and segment not in _ALLOWED_DOT_PREFIXES
        ):
            raise ValidationError(f"Path contains unsafe segment: {segment}")


def assert_path_limits(path: str) -> None:
    """Step 3: Enforce max length and depth.

    The depth limit applies only to relative paths.  Absolute paths have
    system-level components (e.g. /private/var/folders/…/T/tmpXXXX) that
    exceed MAX_DIRECTORY_DEPTH on macOS even for shallow repository files,
    so we skip the depth check when the path is already absolute.  Absolute
    paths only reach this function when safe_read_file re-validates an
    already-validated abs_path for defense-in-depth; the relative-path check
    already enforced depth when the path was first validated.
    """
    if len(path) > MAX_PATH_LENGTH:
        raise ValidationError(
            f"Path exceeds maximum length ({len(path)} > {MAX_PATH_LENGTH})"
        )
    p = Path(path)
    if not p.is_absolute():
        depth = len(p.parts)
        if depth > MAX_DIRECTORY_DEPTH:
            raise ValidationError(
                f"Path exceeds maximum depth ({depth} > {MAX_DIRECTORY_DEPTH})"
            )


def is_within(root: Path | str, path: Path | str) -> bool:
    """Return True if *path* is strictly inside *root* (not equal, not a sibling).

    Both arguments must already be resolved absolute paths.
    Uses an ``os.sep`` guard to prevent prefix-only matches
    (e.g. ``/foo/bar`` should not match root ``/foo/b``).
    """
    return str(path).startswith(str(root) + os.sep)


def assert_inside_root(full_path: str, root: str) -> None:
    """Step 5: Strict containment check with os.sep guard."""
    if root == os.sep or root == "/":
        raise ValidationError("Root cannot be filesystem root")
    if not full_path.startswith(root + os.sep):
        raise ValidationError("Path resolves outside root directory")


def assert_no_symlinked_parents(full_path: str, root: str) -> None:
    """Step 6: Walk each parent directory, reject any symlinks."""
    current = Path(full_path).parent
    root_path = Path(root)
    while current != root_path and current != current.parent:
        if current.is_symlink():
            raise ValidationError(
                "Path contains symlink in parent chain"
            )
        current = current.parent


def _assert_relative_hidden_segments(full_path: str, resolved_root: str) -> None:
    """Post-resolution hidden-segment check on the repo-relative portion only.

    Computes the path RELATIVE TO resolved_root on the RESOLVED (post-symlink)
    full_path and rejects any segment that starts with '.' (beyond the allowed
    list) in that relative tail.  This is the authoritative hidden-file gate
    because:

    1. It ignores the trusted storage-root prefix (e.g. ~/.code-index) entirely,
       so the original .code-index root-prefix bug stays fixed.
    2. It operates on the resolved path, so a symlink from a clean relative name
       (public.txt) to a hidden target (.env) is caught after symlink resolution.
    3. It runs for both the relative-input call (validate_file_access) and the
       absolute-input re-validation call (safe_read_file), covering every call
       site (get_symbol, search_references, scan_security, search_text) without
       changes to callers.

    assert_inside_root MUST have passed before this is called so full_path is
    guaranteed to be strictly inside resolved_root; therefore '..' cannot
    appear in rel_parts and no additional '..' check is needed here.
    """
    rel = os.path.relpath(full_path, resolved_root)
    for segment in Path(rel).parts:
        if segment == ".":
            continue
        if segment.startswith(".") and segment not in _ALLOWED_DOT_PREFIXES:
            raise ValidationError(f"Path contains unsafe segment: {segment}")


def validate_path(path: str, root: str) -> str:
    """Run the full 6-step validation chain + post-resolution hidden-segment check.

    Returns the resolved absolute path if valid.
    Raises ValidationError if any step fails.

    Steps:
        0. NFC normalization — canonical Unicode form before all checks
        1. assert_no_control_chars — reject C0 (ord < 32), DEL (0x7F), C1 (0x80–0x9F)
        2. assert_safe_segments — reject .., dot-prefixed (early gate; the dot-prefix
           check is skipped for absolute inputs since the authoritative check is the
           post-resolution step 7 below)
        3. assert_path_limits — max 512 chars, 10 depth
        4. Path.resolve() — normalize to absolute
        5. assert_inside_root — strict prefix + os.sep
        6. assert_no_symlinked_parents — lstat walk
        7. _assert_relative_hidden_segments — authoritative hidden-segment check on
           the resolved path relative to resolved_root; catches absolute hidden paths
           in index source_files and symlink-to-hidden-target bypasses
    """
    # Step 0: normalize to NFC so NFD-encoded characters are in canonical form
    # before any string comparison or pattern matching.
    path = unicodedata.normalize("NFC", path)
    # FUZZ-5: Strip BOM (U+FEFF) — it passes control-char checks (ord > 159)
    # but creates invisible path differences on most filesystems.
    path = path.replace("\ufeff", "")
    # Reject backslashes (potential traversal bypass on mixed-OS paths)
    # Must be after NFC normalization to catch backslashes in normalized form.
    if "\\" in path:
        raise ValidationError("Backslashes not allowed in paths")
    assert_no_control_chars(path)
    # Strip ASCII spaces only (not all whitespace — str.strip() would eat
    # control chars that assert_no_control_chars must reject first).
    path = path.strip(" ")
    if not path:
        raise ValidationError("Path must not be empty or whitespace-only")
    assert_safe_segments(path)
    assert_path_limits(path)

    resolved_root = str(Path(root).resolve())
    full_path = str((Path(root) / path).resolve())

    assert_inside_root(full_path, resolved_root)
    assert_no_symlinked_parents(full_path, resolved_root)
    _assert_relative_hidden_segments(full_path, resolved_root)

    return full_path
