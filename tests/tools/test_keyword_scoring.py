"""Tests for keyword scoring improvements: compound splitting + stemming."""

from codesight_mcp.tools._common import _split_identifier, _stem, calculate_symbol_score


class TestSplitIdentifier:
    def test_snake_case(self):
        assert _split_identifier("hash_password") == {"hash", "password"}

    def test_camel_case(self):
        assert _split_identifier("AuthManager") == {"auth", "manager"}

    def test_mixed_case(self):
        result = _split_identifier("getHTTPResponse")
        assert "get" in result
        assert "response" in result

    def test_single_word(self):
        assert _split_identifier("login") == {"login"}

    def test_all_caps(self):
        assert _split_identifier("HTTP") == {"http"}

    def test_with_numbers(self):
        assert _split_identifier("base64_encode") == {"base64", "encode"}

    def test_empty_string(self):
        assert _split_identifier("") == set()

    def test_underscores_only(self):
        assert _split_identifier("___") == set()


class TestStem:
    def test_ing_suffix(self):
        assert _stem("hashing") == _stem("hash")

    def test_ation_suffix(self):
        assert _stem("validation") == _stem("validate")

    def test_s_suffix(self):
        assert _stem("functions") == _stem("function")

    def test_short_words_unchanged(self):
        assert _stem("get") == "get"

    def test_ed_suffix(self):
        assert _stem("parsed") == _stem("parse")

    def test_er_suffix(self):
        assert _stem("parser") == _stem("parse")

    def test_already_stemmed(self):
        assert _stem("hash") == "hash"


class TestIntentQueryScoring:
    """Verify that intent-based queries now score > 0 for relevant symbols."""

    def _make_sym(self, name, signature="", summary="", docstring="", keywords=None):
        return {
            "name": name, "signature": signature, "summary": summary,
            "docstring": docstring, "keywords": keywords or [],
        }

    def test_password_hashing_matches_hash_password(self):
        sym = self._make_sym(
            "hash_password",
            "def hash_password(password: str) -> str:",
            "Hash a password using bcrypt",
        )
        score = calculate_symbol_score(sym, "password hashing", {"password", "hashing"})
        assert score > 0, "Intent query 'password hashing' should match hash_password"

    def test_file_parser_matches_parse_file(self):
        sym = self._make_sym(
            "parse_file",
            "def parse_file(path: str) -> AST:",
            "Parse a source file into an AST",
        )
        score = calculate_symbol_score(sym, "file parser", {"file", "parser"})
        assert score > 0, "Intent query 'file parser' should match parse_file"

    def test_auth_manager_matches_authentication(self):
        sym = self._make_sym(
            "AuthManager",
            "class AuthManager:",
            "Manages user authentication",
        )
        score = calculate_symbol_score(sym, "authentication manager", {"authentication", "manager"})
        assert score > 0, "Intent query 'authentication manager' should match AuthManager"

    def test_existing_exact_match_still_works(self):
        """Ensure existing exact-name matching still gets highest scores."""
        sym = self._make_sym("login", "def login():", "User login")
        score = calculate_symbol_score(sym, "login", {"login"})
        assert score >= 20, "Exact name match should still score 20+"

    def test_existing_substring_match_still_works(self):
        """Ensure existing substring matching still works."""
        sym = self._make_sym("user_login", "def user_login():", "Login the user")
        score = calculate_symbol_score(sym, "login", {"login"})
        assert score >= 10, "Substring match should still score 10+"

    def test_unrelated_query_still_scores_zero(self):
        """Unrelated queries should still score 0."""
        sym = self._make_sym("calculate_tax", "def calculate_tax(amount):", "Calculate tax")
        score = calculate_symbol_score(sym, "network socket", {"network", "socket"})
        assert score == 0, "Unrelated query should score 0"
