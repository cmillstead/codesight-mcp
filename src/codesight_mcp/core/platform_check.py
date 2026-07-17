"""Fail fast with a clear message on non-POSIX platforms (GP#15)."""

import os


def _is_posix(name: str) -> bool:
    """Pure predicate — True iff the given os.name denotes a POSIX platform."""
    return name == "posix"


def _require_posix(name: str) -> None:
    """Raise RuntimeError with a clear message if `name` is not POSIX. Pure/testable."""
    if not _is_posix(name):
        raise RuntimeError(
            "codesight-mcp requires a POSIX platform (Linux/macOS). It relies on "
            "fcntl.flock, os.getuid, os.fchmod, and O_NOFOLLOW, which are unavailable "
            f"on this OS (os.name={name!r}). Windows is not supported."
        )


def ensure_posix() -> None:
    """Startup guard — call at server/CLI entry before any tool dispatch."""
    _require_posix(os.name)
