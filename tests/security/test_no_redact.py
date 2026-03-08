"""Tests for CODESIGHT_NO_REDACT=1 env var (Task 16)."""

import os
import tempfile

import pytest

from codesight_mcp.security import sanitize_signature_for_api, _no_redact


class TestNoRedactEnvVar:
    """CODESIGHT_NO_REDACT=1 disables inline secret redaction."""

    def test_no_redact_disabled_by_default(self):
        """Without the env var, _no_redact() returns False."""
        old = os.environ.pop("CODESIGHT_NO_REDACT", None)
        try:
            assert _no_redact() is False
        finally:
            if old is not None:
                os.environ["CODESIGHT_NO_REDACT"] = old

    def test_no_redact_enabled_with_1(self, monkeypatch):
        """CODESIGHT_NO_REDACT=1 makes _no_redact() return True."""
        monkeypatch.setenv("CODESIGHT_NO_REDACT", "1")
        assert _no_redact() is True

    def test_no_redact_not_enabled_with_other_values(self, monkeypatch):
        """Only '1' activates no-redact, not 'true' or 'yes'."""
        for val in ("true", "yes", "0", ""):
            monkeypatch.setenv("CODESIGHT_NO_REDACT", val)
            assert _no_redact() is False, f"Value {val!r} should not enable no-redact"

    def test_sanitize_redacts_by_default(self):
        """Without the env var, secrets are redacted normally."""
        old = os.environ.pop("CODESIGHT_NO_REDACT", None)
        try:
            sig = 'API_KEY = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789"'
            result = sanitize_signature_for_api(sig)
            assert "ghp_" not in result
            assert "<REDACTED>" in result
        finally:
            if old is not None:
                os.environ["CODESIGHT_NO_REDACT"] = old

    def test_sanitize_skips_redaction_when_no_redact(self, monkeypatch):
        """With CODESIGHT_NO_REDACT=1, secrets pass through unchanged."""
        monkeypatch.setenv("CODESIGHT_NO_REDACT", "1")
        sig = 'API_KEY = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789"'
        result = sanitize_signature_for_api(sig)
        assert result == sig

    def test_no_redact_preserves_password_defaults(self, monkeypatch):
        """With no-redact, password='hunter2' is preserved."""
        monkeypatch.setenv("CODESIGHT_NO_REDACT", "1")
        sig = 'def connect(host, password="hunter2")'
        result = sanitize_signature_for_api(sig)
        assert "hunter2" in result
        assert result == sig

    def test_no_redact_preserves_del_bytes(self, monkeypatch):
        """With no-redact, DEL/C1 bytes are not stripped either."""
        monkeypatch.setenv("CODESIGHT_NO_REDACT", "1")
        sig = "sk_live_\x7f" + "a" * 24
        result = sanitize_signature_for_api(sig)
        assert result == sig  # returned completely unchanged

    def test_no_redact_checked_at_runtime(self, monkeypatch):
        """The env var is checked on every call, not cached."""
        monkeypatch.setenv("CODESIGHT_NO_REDACT", "1")
        sig = 'token = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789"'
        assert sanitize_signature_for_api(sig) == sig  # no redaction

        monkeypatch.delenv("CODESIGHT_NO_REDACT")
        result = sanitize_signature_for_api(sig)
        assert "ghp_" not in result  # now redacted

    def test_clean_signature_unaffected_by_no_redact(self, monkeypatch):
        """A clean signature is the same with or without no-redact."""
        sig = "def hello(name: str) -> str"
        monkeypatch.setenv("CODESIGHT_NO_REDACT", "1")
        assert sanitize_signature_for_api(sig) == sig
        monkeypatch.delenv("CODESIGHT_NO_REDACT")
        assert sanitize_signature_for_api(sig) == sig
