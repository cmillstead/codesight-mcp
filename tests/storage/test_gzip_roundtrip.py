"""Tests for gzip compression round-trip and edge cases (P1-04 + P2)."""

import gzip
import json

import pytest

from codesight_mcp.storage import IndexStore
from codesight_mcp.storage.index_store import _safe_gzip_decompress
from codesight_mcp.parser import Symbol


def _make_symbol(**overrides) -> Symbol:
    """Build a Symbol with sensible defaults, accepting field overrides."""
    defaults = dict(
        id="test.py::func#function",
        file="test.py",
        name="func",
        qualified_name="func",
        kind="function",
        language="python",
        signature="def func():",
        summary="Does func",
        byte_offset=0,
        byte_length=15,
    )
    defaults.update(overrides)
    return Symbol(**defaults)


class TestGzipRoundTripAllFields:
    """Save and reload an index, verifying every Symbol field survives."""

    def test_all_symbol_fields_preserved(self, tmp_path):
        """Every Symbol field should be identical after save+load round-trip."""
        store = IndexStore(base_path=str(tmp_path))

        sym = Symbol(
            id="test.py::MyClass.login#method",
            file="test.py",
            name="login",
            qualified_name="MyClass.login",
            kind="method",
            language="python",
            signature="def login(self, user: str) -> bool:",
            summary="Authenticate a user",
            docstring="Authenticate the given user and return success.",
            decorators=["@requires_auth", "@log_call"],
            byte_offset=100,
            byte_length=250,
        )

        content = "x" * 350  # Dummy content covering byte range

        store.save_index(
            owner="test",
            name="repo",
            source_files=["test.py"],
            symbols=[sym],
            raw_files={"test.py": content},
            languages={"python": 1},
        )

        loaded = store.load_index("test", "repo")
        assert loaded is not None
        assert len(loaded.symbols) == 1

        s = loaded.symbols[0]
        assert s["id"] == sym.id
        assert s["file"] == sym.file
        assert s["name"] == sym.name
        assert s["qualified_name"] == sym.qualified_name
        assert s["kind"] == sym.kind
        assert s["language"] == sym.language
        assert s["signature"] == sym.signature
        assert s["summary"] == sym.summary
        assert s["docstring"] == sym.docstring
        assert s["decorators"] == sym.decorators
        assert s["byte_offset"] == sym.byte_offset
        assert s["byte_length"] == sym.byte_length


class TestGzipMagicBytes:
    """Verify the saved index file is actually gzip-compressed."""

    def test_index_file_has_gzip_magic_bytes(self, tmp_path):
        """The .json.gz file should start with gzip magic bytes 1f 8b."""
        store = IndexStore(base_path=str(tmp_path))

        store.save_index(
            owner="test",
            name="repo",
            source_files=["main.py"],
            symbols=[_make_symbol()],
            raw_files={"main.py": "def func(): pass"},
            languages={"python": 1},
        )

        # Find the .json.gz file
        gz_files = list(tmp_path.rglob("*.json.gz"))
        assert len(gz_files) == 1, f"Expected exactly one .json.gz file, found {len(gz_files)}"

        with open(gz_files[0], "rb") as f:
            magic = f.read(2)
        assert magic == b"\x1f\x8b", f"Expected gzip magic bytes, got {magic!r}"


class TestSafeGzipDecompress:
    """Tests for _safe_gzip_decompress decompression bomb protection."""

    def test_rejects_decompression_bomb(self):
        """Data that decompresses beyond max_size should raise ValueError."""
        # Create a small gzip payload that decompresses to 1000 bytes
        small_data = gzip.compress(b"x" * 1000)
        # Set max_size below the decompressed size to trigger rejection
        with pytest.raises(ValueError, match="exceeds maximum size"):
            _safe_gzip_decompress(small_data, max_size=500)

    def test_accepts_data_within_limit(self):
        """Data within the max_size limit should decompress successfully."""
        payload = b"hello world"
        compressed = gzip.compress(payload)
        result = _safe_gzip_decompress(compressed, max_size=1000)
        assert result == payload

    def test_accepts_data_at_exact_limit(self):
        """Data exactly at max_size should succeed (boundary condition)."""
        payload = b"x" * 500
        compressed = gzip.compress(payload)
        result = _safe_gzip_decompress(compressed, max_size=500)
        assert result == payload


class TestLegacyJsonFallback:
    """load_index falls back to legacy uncompressed .json when .json.gz is absent."""

    def test_loads_legacy_uncompressed_json(self, tmp_path):
        """If only a .json file exists (no .json.gz), load_index should read it."""
        store = IndexStore(base_path=str(tmp_path))

        # First save normally (creates .json.gz)
        store.save_index(
            owner="test",
            name="repo",
            source_files=["main.py"],
            symbols=[_make_symbol()],
            raw_files={"main.py": "def func(): pass"},
            languages={"python": 1},
        )

        # Find and read the compressed index
        gz_files = list(tmp_path.rglob("*.json.gz"))
        assert len(gz_files) == 1
        gz_path = gz_files[0]

        with open(gz_path, "rb") as f:
            raw = f.read()
        data = json.loads(gzip.decompress(raw))

        # Write as legacy .json (uncompressed)
        legacy_path = gz_path.with_suffix("")  # remove .gz -> .json
        with open(legacy_path, "w") as f:
            json.dump(data, f)

        # Remove the .gz file
        gz_path.unlink()

        # load_index should fall back to the .json file
        loaded = store.load_index("test", "repo")
        assert loaded is not None
        assert loaded.repo == "test/repo"
        assert len(loaded.symbols) == 1


class TestLegacyJsonCleanup:
    """save_index removes legacy .json file when .json.gz is written."""

    def test_removes_legacy_json_on_save(self, tmp_path):
        """After saving, any legacy .json file alongside .json.gz should be removed."""
        store = IndexStore(base_path=str(tmp_path))

        # Save to create .json.gz
        store.save_index(
            owner="test",
            name="repo",
            source_files=["main.py"],
            symbols=[_make_symbol()],
            raw_files={"main.py": "def func(): pass"},
            languages={"python": 1},
        )

        # Manually create a legacy .json file alongside the .json.gz
        gz_files = list(tmp_path.rglob("*.json.gz"))
        assert len(gz_files) == 1
        legacy_path = gz_files[0].with_suffix("")  # .json
        legacy_path.write_text("{}")

        # Save again -- should clean up the legacy file
        store.save_index(
            owner="test",
            name="repo",
            source_files=["main.py"],
            symbols=[_make_symbol()],
            raw_files={"main.py": "def func(): pass"},
            languages={"python": 1},
        )

        assert not legacy_path.exists(), "Legacy .json should be removed after save"
        assert gz_files[0].exists(), ".json.gz should still exist"


class TestRoundTripEmptySymbols:
    """Round-trip with an empty symbols list."""

    def test_empty_symbols_roundtrip(self, tmp_path):
        """An index with zero symbols should survive save+load."""
        store = IndexStore(base_path=str(tmp_path))

        store.save_index(
            owner="test",
            name="repo",
            source_files=["empty.py"],
            symbols=[],
            raw_files={"empty.py": ""},
            languages={"python": 1},
        )

        loaded = store.load_index("test", "repo")
        assert loaded is not None
        assert loaded.symbols == []
        assert loaded.source_files == ["empty.py"]


class TestRoundTripSpecialCharacters:
    """Round-trip with symbols containing special characters."""

    def test_unicode_in_signature_and_summary(self, tmp_path):
        """Unicode and newlines in Symbol fields should survive round-trip."""
        store = IndexStore(base_path=str(tmp_path))

        sym = _make_symbol(
            name="greet",
            signature='def greet(name: str = "world") -> str:',
            summary="Returns a greeting with emoji-like chars and accents: cafe",
            docstring="Multi-line docstring.\nLine two.\nLine three.",
        )

        store.save_index(
            owner="test",
            name="repo",
            source_files=["test.py"],
            symbols=[sym],
            raw_files={"test.py": "def greet(): pass"},
            languages={"python": 1},
        )

        loaded = store.load_index("test", "repo")
        assert loaded is not None
        s = loaded.symbols[0]
        assert s["name"] == "greet"
        assert "cafe" in s["summary"]
        assert "Line two." in s["docstring"]


class TestRoundTripFileHashes:
    """Round-trip preserves file_hashes and content_hash."""

    def test_file_hashes_preserved(self, tmp_path):
        """file_hashes dict should survive save+load round-trip."""
        store = IndexStore(base_path=str(tmp_path))

        content = "def func(): pass"

        store.save_index(
            owner="test",
            name="repo",
            source_files=["test.py"],
            symbols=[_make_symbol()],
            raw_files={"test.py": content},
            languages={"python": 1},
        )

        loaded = store.load_index("test", "repo")
        assert loaded is not None
        # file_hashes should be populated (auto-computed from raw_files)
        assert "test.py" in loaded.file_hashes
        # Should be a 64-char hex string (SHA-256)
        assert len(loaded.file_hashes["test.py"]) == 64

    def test_explicit_file_hashes_preserved(self, tmp_path):
        """Explicitly provided file_hashes should be stored and loadable."""
        store = IndexStore(base_path=str(tmp_path))

        explicit_hash = "a" * 64  # valid 64-char hex

        store.save_index(
            owner="test",
            name="repo",
            source_files=["test.py"],
            symbols=[_make_symbol()],
            raw_files={"test.py": "def func(): pass"},
            languages={"python": 1},
            file_hashes={"test.py": explicit_hash},
        )

        loaded = store.load_index("test", "repo")
        assert loaded is not None
        assert loaded.file_hashes["test.py"] == explicit_hash
