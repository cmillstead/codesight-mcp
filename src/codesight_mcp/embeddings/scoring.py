"""Scoring utilities for hybrid keyword + semantic search ranking.

Provides cosine similarity and a hybrid ranking function that blends
keyword scores with cosine similarity using a configurable weight.
"""

import math

# Approximate upper bound for single-term keyword queries against the FTS index.
# Used to normalize raw keyword scores into [0, 1] for blending with cosine similarity.
# Phase 2 hybrid search should consider candidate-set-relative normalization
# for multi-word queries, where raw scores can exceed this value significantly.
KEYWORD_SCORE_NORMALIZATION_MAX = 40.0


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Returns 0.0 for empty vectors or zero-norm vectors.
    Uses zip() so mismatched lengths silently truncate to the shorter vector.
    """
    if not a or not b:
        return 0.0

    dot = 0.0
    norm_a_sq = 0.0
    norm_b_sq = 0.0

    for ai, bi in zip(a, b):
        dot += ai * bi
        norm_a_sq += ai * ai
        norm_b_sq += bi * bi

    norm_a = math.sqrt(norm_a_sq)
    norm_b = math.sqrt(norm_b_sq)

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)


def hybrid_rank(keyword_score: float, cosine_sim: float, semantic_weight: float = 0.7) -> float:
    """Blend a raw keyword score with cosine similarity into a single rank.

    The keyword_score is normalized to [0, 1] by dividing by
    KEYWORD_SCORE_NORMALIZATION_MAX and capping at 1.0.  The final score is:

        keyword_normalized * (1 - semantic_weight) + cosine_sim * semantic_weight
    """
    keyword_normalized = min(keyword_score / KEYWORD_SCORE_NORMALIZATION_MAX, 1.0)
    return keyword_normalized * (1.0 - semantic_weight) + cosine_sim * semantic_weight
