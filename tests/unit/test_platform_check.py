import pytest

from codesight_mcp.core import platform_check


def test_is_posix_true_for_posix():
    assert platform_check._is_posix("posix") is True


def test_is_posix_false_for_nt():
    assert platform_check._is_posix("nt") is False


def test_require_posix_raises_on_non_posix():
    with pytest.raises(RuntimeError, match="POSIX"):
        platform_check._require_posix("nt")


def test_require_posix_passes_on_posix():
    platform_check._require_posix("posix")  # no raise


def test_ensure_posix_passes_on_this_host():
    platform_check.ensure_posix()  # POSIX CI/dev host — no raise
