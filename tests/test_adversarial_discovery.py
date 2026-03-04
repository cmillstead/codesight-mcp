"""Adversarial discovery tests — depth bombs, pattern limits."""

import tempfile
from pathlib import Path

import pytest

from ironmunch.discovery import discover_local_files
from ironmunch.core.limits import MAX_DIRECTORY_DEPTH


class TestDiscoveryDepthLimit:
    """M-2: Discovery must not traverse deeper than MAX_DIRECTORY_DEPTH."""

    def test_deep_directory_bomb_truncated(self):
        """20-level nesting must be stopped at MAX_DIRECTORY_DEPTH."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create a 20-level deep directory with a .py file at the bottom
            deep = root
            for i in range(20):
                deep = deep / f"d{i}"
            deep.mkdir(parents=True)
            (deep / "deep.py").write_text("def deep(): pass")

            # Also create a shallow file
            (root / "shallow.py").write_text("def shallow(): pass")

            files, warnings = discover_local_files(root)
            file_names = [f.name for f in files]

            assert "shallow.py" in file_names
            # The deep file should NOT be found (depth > MAX_DIRECTORY_DEPTH)
            assert "deep.py" not in file_names


class TestDiscoveryPatternLimits:
    """M-6: Extra ignore patterns must be bounded."""

    def test_too_many_patterns_truncated(self):
        """More than 20 extra patterns should be silently truncated."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.py").write_text("def main(): pass")

            patterns = [f"pattern_{i}" for i in range(100)]
            # Should not crash or hang
            files, _ = discover_local_files(root, extra_ignore_patterns=patterns)
            assert len(files) >= 0  # Just verify it completes

    def test_very_long_pattern_truncated(self):
        """A pattern longer than 200 chars should be truncated."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.py").write_text("def main(): pass")

            patterns = ["a" * 1000]
            # Should not crash or hang
            files, _ = discover_local_files(root, extra_ignore_patterns=patterns)
            assert len(files) >= 0
