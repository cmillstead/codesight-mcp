---
name: Injection defense — wrapper primary, phrase filter secondary, weak-override posture
description: The untrusted-content wrapper is the primary injection boundary; the phrase matcher is a secondary summary-blanking filter tuned for low false positives (override/important:/you are stay corroborated-weak), so residual matcher recall gaps are accepted rather than chased into over-matching
type: project
---

## Context
Indexed docstrings / AI summaries are attacker-influenceable and flow into prompts. Two layers defend this: (1) `wrap_untrusted_content` frames ALL disk-derived content in `<<<UNTRUSTED_CODE_…>>>` markers; (2) `_contains_injection_phrase` (`summarizer/batch_summarize.py`) blanks summaries that look like injection. Audit item 6 rewrote layer 2 from a broad case-insensitive **substring** matcher to a word-boundary / role-context **grammar** (strong tier, corroborated-weak tier, and `_INJECTION_SIGNATURE_PATTERN`). The rewrite fixed real over-matching (`"Override the default timeout"` no longer flagged) but a substring matcher and a precise grammar cannot have the same recall.

## Decision
**The wrapper is the PRIMARY boundary; the phrase filter is SECONDARY (summary-blanking only).** `override`, `important:`, `you are`, and bare `assistant` stay **corroborated-weak** — each fires only when a strong phrase or a second distinct weak phrase co-occurs — specifically to spare benign prose. Strong multi-word injection signatures (`_INJECTION_SIGNATURE_PATTERN`: verb + quantifiers + positions+ + object, either order, possessive determiners allowed) carry the recall for genuine `override …instructions` attacks. When a reviewer flags a missed phrasing, classify it: a **signature-grammar bug** (e.g. single-position-word limit, missing possessive) is fixed within the grammar; a **bare-token recall gap** that only broad-substring `override` would catch is the ACCEPTED cost of the weak posture — surfaced to the user, never closed by re-broadening `override` to strong.

## Alternatives Considered
- **Keep `override` etc. strong/substring** — rejected: reintroduces the benign `"Override the default timeout"` false positive that blanks legitimate docstrings.
- **Single-token FP blanking (drop the ambiguous tokens entirely)** — rejected by the user previously (see the `injection-filter-posture` memory).
- **Chase every phrasing variant into the grammar** — rejected: a grammar always misses some form; the tail is unbounded and each addition risks new over-match.

## Constraints
- Preserve all Unicode normalization (Cf-strip → NFKD → confusable-fold → lower + ASCII-fold) so homoglyph attacks still match.
- Telemetry is rule-ID-keyed and bounded; NEVER log matched user text.
- Every grammar change must ship both an attack-caught test AND a benign-not-flagged FP-guard test.

## Consequences
If someone "hardens" the matcher by promoting `override` back to strong or by chasing the phrasing tail without the FP-guard discipline, they resurrect benign false positives (blanked legitimate summaries) and destabilize the tier the whole design depends on. The correct response to a residual recall gap is to confirm the wrapper still frames the content (it does) and accept the gap — not to broaden the secondary filter. See PR #65 (4 review rounds, 3 recall regressions fixed, tail accepted) and the `injection-matcher-recall-tradeoff` + `injection-filter-posture` memories.
