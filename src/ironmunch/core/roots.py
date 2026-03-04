"""Immutable root path management — ported from basalt-mcp.

Root paths are resolved once at startup to their canonical form
(symlinks resolved). Access via get_storage_root() which throws
if called before initialization.
"""

from pathlib import Path


class RootNotInitializedError(RuntimeError):
    """Raised when get_storage_root() is called before init_storage_root()."""
    pass


_storage_root: str | None = None


def init_storage_root(path: str) -> str:
    """Initialize the storage root path.

    Resolves to canonical absolute path (symlinks resolved).
    Validates the path exists and is a directory.
    Raises RuntimeError if already initialized.

    Returns the resolved path.
    """
    global _storage_root

    if _storage_root is not None:
        raise RuntimeError("Storage root already initialized")

    p = Path(path)
    if not p.exists():
        raise ValueError(f"Storage root does not exist: {path}")
    if not p.is_dir():
        raise ValueError(f"Storage root is not a directory: {path}")

    _storage_root = str(p.resolve())
    return _storage_root


def get_storage_root() -> str:
    """Get the initialized storage root path.

    Raises RootNotInitializedError if init_storage_root() hasn't been called.
    """
    if _storage_root is None:
        raise RootNotInitializedError(
            "Storage root not initialized. Call init_storage_root() first."
        )
    return _storage_root
