"""Tests for core.rate_limiting module."""

import time

from codesight_mcp.core.rate_limiting import _rate_limit, _rate_limit_state_dir


def test_rate_limit_allows_first_call(tmp_path):
    assert _rate_limit("test_tool", str(tmp_path)) is True


def test_rate_limit_state_dir_uses_storage_path(tmp_path):
    result = _rate_limit_state_dir(str(tmp_path))
    assert result == tmp_path


def test_rate_limit_respects_per_tool_limit(tmp_path):
    for _ in range(60):
        assert _rate_limit("test_tool", str(tmp_path)) is True
    assert _rate_limit("test_tool", str(tmp_path)) is False
    assert _rate_limit("other_tool", str(tmp_path)) is True


def _drive_fail_closed(state_dir):
    """Drive the rate limiter into fail-closed using a real filesystem obstacle.

    Creates a directory at the .rate_limits.json path so atomic_write_nofollow
    raises IsADirectoryError on rename, causing real write failures.
    Returns the blocker path for cleanup.
    """
    from codesight_mcp.core import rate_limiting

    blocker = state_dir / ".rate_limits.json"
    blocker.mkdir(exist_ok=True)

    for idx in range(rate_limiting._MAX_WRITE_FAILURES):
        _rate_limit(f"fail_tool_{idx}", str(state_dir))

    assert rate_limiting._consecutive_write_failures >= rate_limiting._MAX_WRITE_FAILURES
    return blocker


def _reset_rate_limiter():
    """Reset rate limiter module globals to a clean state."""
    from codesight_mcp.core import rate_limiting
    rate_limiting._consecutive_write_failures = 0
    rate_limiting._last_failure_time = 0.0


def test_rate_limit_fails_closed_after_threshold(tmp_path):
    """After consecutive write failures, rate_limit should deny calls."""

    _reset_rate_limiter()

    blocker = _drive_fail_closed(tmp_path)

    # After threshold, should fail closed
    result = _rate_limit("tool_blocked", str(tmp_path))
    assert result is False, "Should deny after too many write failures"

    # Clean up
    blocker.rmdir()
    _reset_rate_limiter()


def test_rate_limiter_stays_closed_during_timeout_window(tmp_path):
    """Rate limiter should remain closed within the recovery timeout window."""
    from codesight_mcp.core import rate_limiting

    _reset_rate_limiter()

    blocker = _drive_fail_closed(tmp_path)

    # Set last_failure_time to "just now" so we're inside the timeout window
    rate_limiting._last_failure_time = time.time()

    # Should still be denied -- recovery timeout hasn't elapsed
    assert _rate_limit("probe_tool", str(tmp_path)) is False

    # Clean up
    blocker.rmdir()
    _reset_rate_limiter()


def test_rate_limiter_recovers_after_timeout(tmp_path):
    """Rate limiter should allow a probe call after the recovery timeout elapses,
    and a successful write should clear the failure state."""
    from codesight_mcp.core import rate_limiting

    _reset_rate_limiter()

    blocker = _drive_fail_closed(tmp_path)

    # Remove the blocker so writes can succeed during recovery
    blocker.rmdir()

    # Also remove any stale .rate_limits.json file left from failed writes
    state_file = tmp_path / ".rate_limits.json"
    if state_file.exists():
        state_file.unlink()

    # Simulate that the last failure was 61 seconds ago (past recovery timeout)
    rate_limiting._last_failure_time = time.time() - 61

    # The next call should be allowed (recovery probe) and the write should
    # succeed since the blocker directory has been removed.
    result = _rate_limit("recovery_tool", str(tmp_path))
    assert result is True, "Should allow call after recovery timeout"
    assert rate_limiting._consecutive_write_failures == 0, "Successful write should clear failures"
    assert rate_limiting._last_failure_time == 0.0, "Successful recovery should reset failure time"

    _reset_rate_limiter()


def test_rate_limiter_re_enters_fail_closed_on_failed_recovery(tmp_path):
    """If the recovery probe write also fails, re-enter fail-closed with a new timeout."""
    from codesight_mcp.core import rate_limiting

    _reset_rate_limiter()

    blocker = _drive_fail_closed(tmp_path)

    # Simulate timeout elapsed
    rate_limiting._last_failure_time = time.time() - 61

    # Blocker is still in place, so the recovery probe write will also fail.
    result = _rate_limit("recovery_tool", str(tmp_path))
    # The call itself is allowed through (returns True) but the write failure
    # increments the counter and updates the timestamp
    assert result is True, "Recovery probe call is allowed through"

    # Failure counter should still be at/above threshold (re-armed)
    assert rate_limiting._consecutive_write_failures >= rate_limiting._MAX_WRITE_FAILURES
    # _last_failure_time should be recent (re-armed for another timeout)
    assert rate_limiting._last_failure_time > time.time() - 5

    # Immediately after, should be denied again (within new timeout window)
    assert _rate_limit("blocked_tool", str(tmp_path)) is False

    # Clean up
    blocker.rmdir()
    _reset_rate_limiter()
