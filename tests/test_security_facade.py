"""Tests for the security facade."""

import tempfile
from pathlib import Path

import pytest

from ironmunch.security import (
    validate_file_access,
    safe_read_file,
    is_secret_file,
    is_binary_file,
    is_binary_content,
    should_exclude_file,
    sanitize_repo_identifier,
)
from ironmunch.core.validation import ValidationError


class TestValidateFileAccess:
    def test_valid_file(self):
        with tempfile.TemporaryDirectory() as root:
            f = Path(root) / "src" / "main.py"
            f.parent.mkdir()
            f.touch()
            result = validate_file_access("src/main.py", root)
            assert str(Path(root).resolve()) in result

    def test_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as root:
            with pytest.raises(ValidationError):
                validate_file_access("../../etc/passwd", root)


class TestSafeReadFile:
    def test_read_valid(self):
        with tempfile.TemporaryDirectory() as root:
            f = Path(root) / "hello.py"
            f.write_text("print('hello')", encoding="utf-8")
            content = safe_read_file(str(f), root)
            assert content == "print('hello')"

    def test_read_invalid_utf8(self):
        with tempfile.TemporaryDirectory() as root:
            f = Path(root) / "binary.py"
            f.write_bytes(b"hello \xff world")
            content = safe_read_file(str(f), root)
            assert "hello" in content  # errors="replace" mode

    def test_read_oversized_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            f = Path(root) / "big.py"
            f.write_bytes(b"x" * (600 * 1024))  # 600 KB > 500 KB limit
            with pytest.raises(ValidationError, match="maximum size"):
                safe_read_file(str(f), root)


class TestSecretDetection:
    def test_env_file(self):
        assert is_secret_file(".env")

    def test_pem_file(self):
        assert is_secret_file("cert.pem")

    def test_key_file(self):
        assert is_secret_file("server.key")

    def test_normal_file(self):
        assert not is_secret_file("main.py")

    def test_id_rsa(self):
        assert is_secret_file("id_rsa")


class TestBinaryDetection:
    def test_image(self):
        assert is_binary_file("photo.png")

    def test_executable(self):
        assert is_binary_file("program.exe")

    def test_python(self):
        assert not is_binary_file("main.py")

    def test_binary_content_with_null(self):
        assert is_binary_content(b"hello\x00world")

    def test_text_content(self):
        assert not is_binary_content(b"hello world")


class TestShouldExclude:
    def test_secret_excluded(self):
        assert should_exclude_file(".env") == "secret_file"

    def test_binary_excluded(self):
        assert should_exclude_file("image.png") == "binary_file"

    def test_normal_not_excluded(self):
        assert should_exclude_file("main.py") is None


class TestRepoIdentifier:
    def test_valid(self):
        assert sanitize_repo_identifier("my-repo") == "my-repo"

    def test_valid_with_dots(self):
        assert sanitize_repo_identifier("my.repo") == "my.repo"

    def test_valid_with_underscore(self):
        assert sanitize_repo_identifier("my_repo") == "my_repo"

    def test_traversal_rejected(self):
        with pytest.raises(ValidationError):
            sanitize_repo_identifier("../etc")

    def test_slash_rejected(self):
        with pytest.raises(ValidationError):
            sanitize_repo_identifier("repo/evil")

    def test_null_byte_rejected(self):
        with pytest.raises(ValidationError):
            sanitize_repo_identifier("repo\x00evil")

    def test_empty_rejected(self):
        with pytest.raises(ValidationError):
            sanitize_repo_identifier("")

    def test_space_rejected(self):
        with pytest.raises(ValidationError):
            sanitize_repo_identifier("repo name")

    def test_semicolon_rejected(self):
        with pytest.raises(ValidationError):
            sanitize_repo_identifier("repo;rm -rf /")
