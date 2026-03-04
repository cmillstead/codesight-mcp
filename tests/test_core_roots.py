"""Tests for immutable root path management."""

import tempfile
from pathlib import Path

import pytest

import ironmunch.core.roots as roots_mod
from ironmunch.core.roots import init_storage_root, get_storage_root, RootNotInitializedError


@pytest.fixture(autouse=True)
def _reset_storage_root():
    """Reset _storage_root before each test so init_storage_root can be called."""
    old = roots_mod._storage_root
    roots_mod._storage_root = None
    yield
    roots_mod._storage_root = old


def test_get_before_init_raises():
    """Must call init before get."""
    with pytest.raises(RootNotInitializedError):
        get_storage_root()


def test_init_and_get():
    with tempfile.TemporaryDirectory() as tmp:
        root = init_storage_root(tmp)
        assert root == str(Path(tmp).resolve())
        assert get_storage_root() == root


def test_init_resolves_symlinks():
    with tempfile.TemporaryDirectory() as tmp:
        real = Path(tmp) / "real"
        real.mkdir()
        link = Path(tmp) / "link"
        link.symlink_to(real)
        root = init_storage_root(str(link))
        assert root == str(real.resolve())


def test_init_nonexistent_raises():
    with pytest.raises(ValueError, match="does not exist"):
        init_storage_root("/nonexistent/path/that/does/not/exist")


def test_init_file_not_dir_raises():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "file.txt"
        f.touch()
        with pytest.raises(ValueError, match="not a directory"):
            init_storage_root(str(f))
