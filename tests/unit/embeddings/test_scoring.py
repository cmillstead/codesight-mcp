"""Tests for codesight_mcp.embeddings.scoring — cosine similarity and hybrid ranking."""

import pytest

from codesight_mcp.embeddings.scoring import (
    KEYWORD_SCORE_NORMALIZATION_MAX,
    cosine_similarity,
    hybrid_rank,
)


# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    """Core behaviour and edge cases for cosine_similarity."""

    def test_identical_vectors_return_one(self):
        assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors_return_zero(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors_return_negative_one(self):
        assert cosine_similarity([1.0, 2.0], [-1.0, -2.0]) == pytest.approx(-1.0)

    def test_zero_vector_a_returns_zero(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_zero_vector_b_returns_zero(self):
        assert cosine_similarity([1.0, 2.0], [0.0, 0.0]) == 0.0

    def test_both_zero_vectors_return_zero(self):
        assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0

    def test_single_element_vectors(self):
        assert cosine_similarity([5.0], [3.0]) == pytest.approx(1.0)

    def test_single_element_opposite(self):
        assert cosine_similarity([5.0], [-3.0]) == pytest.approx(-1.0)

    def test_known_triangle_3_4_vs_4_3(self):
        # cos(theta) for (3, 4) and (4, 3): dot=24, |a|=5, |b|=5 → 24/25
        expected = 24.0 / 25.0
        assert cosine_similarity([3.0, 4.0], [4.0, 3.0]) == pytest.approx(expected)

    def test_empty_vector_a_returns_zero(self):
        assert cosine_similarity([], [1.0, 2.0]) == 0.0

    def test_empty_vector_b_returns_zero(self):
        assert cosine_similarity([1.0, 2.0], []) == 0.0

    def test_both_empty_vectors_return_zero(self):
        assert cosine_similarity([], []) == 0.0

    def test_mismatched_lengths_truncate_to_shorter(self):
        # [1, 0] vs [1] → treats as single-element, both positive → 1.0
        result = cosine_similarity([1.0, 0.0], [1.0])
        assert result == pytest.approx(1.0)

    def test_mismatched_lengths_do_not_crash(self):
        # Should not raise regardless of length mismatch
        result = cosine_similarity([1.0, 2.0, 3.0], [4.0, 5.0])
        assert isinstance(result, float)

    def test_very_large_values(self):
        big = 1e15
        assert cosine_similarity([big, big], [big, big]) == pytest.approx(1.0)

    def test_very_small_values(self):
        tiny = 1e-15
        assert cosine_similarity([tiny, tiny], [tiny, tiny]) == pytest.approx(1.0)

    def test_negative_cosine_passes_through(self):
        # Vectors with angle > 90 degrees
        result = cosine_similarity([1.0, 0.0], [-1.0, 0.1])
        assert result < 0.0


# ---------------------------------------------------------------------------
# hybrid_rank
# ---------------------------------------------------------------------------


class TestHybridRank:
    """Core behaviour and edge cases for hybrid_rank."""

    def test_weight_zero_is_pure_keyword(self):
        keyword_score = 20.0
        cosine_sim = 0.9
        expected = keyword_score / KEYWORD_SCORE_NORMALIZATION_MAX
        assert hybrid_rank(keyword_score, cosine_sim, semantic_weight=0.0) == pytest.approx(expected)

    def test_weight_one_is_pure_semantic(self):
        cosine_sim = 0.85
        assert hybrid_rank(999.0, cosine_sim, semantic_weight=1.0) == pytest.approx(cosine_sim)

    def test_default_weight_is_0_7(self):
        keyword_score = 20.0
        cosine_sim = 0.8
        keyword_normalized = keyword_score / KEYWORD_SCORE_NORMALIZATION_MAX
        expected = keyword_normalized * 0.3 + cosine_sim * 0.7
        assert hybrid_rank(keyword_score, cosine_sim) == pytest.approx(expected)

    def test_keyword_normalization_caps_at_one(self):
        # Score 80 exceeds KEYWORD_SCORE_NORMALIZATION_MAX (40), should cap at 1.0
        cosine_sim = 0.5
        expected = 1.0 * 0.3 + cosine_sim * 0.7
        assert hybrid_rank(80.0, cosine_sim) == pytest.approx(expected)

    def test_keyword_zero_returns_semantic_contribution_only(self):
        cosine_sim = 0.9
        expected = cosine_sim * 0.7
        assert hybrid_rank(0.0, cosine_sim) == pytest.approx(expected)

    def test_both_zero_returns_zero(self):
        assert hybrid_rank(0.0, 0.0) == 0.0

    def test_negative_cosine_sim_passes_through(self):
        # Negative cosine similarity should reduce the blended score
        result = hybrid_rank(20.0, -0.5)
        keyword_normalized = 20.0 / KEYWORD_SCORE_NORMALIZATION_MAX
        expected = keyword_normalized * 0.3 + (-0.5) * 0.7
        assert result == pytest.approx(expected)

    def test_exact_normalization_max_gives_one(self):
        # keyword_score == KEYWORD_SCORE_NORMALIZATION_MAX → normalized to exactly 1.0
        cosine_sim = 0.0
        expected = 1.0 * 0.3
        assert hybrid_rank(KEYWORD_SCORE_NORMALIZATION_MAX, cosine_sim) == pytest.approx(expected)
