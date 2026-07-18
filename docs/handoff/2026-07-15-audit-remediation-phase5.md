# Handoff — audit-remediation Phase 5 (mid-execution)

**Written 2026-07-15. Resumes at Task 3.** Supersedes `2026-07-15-audit-remediation.md` (that one was end-of-Phase-4).

## How to resume
This is a `/coding-team` Phase 5 execution run. Re-invoke `/coding-team` with "resume Phase 5 — plan docs/plans/2026-07-15-audit-remediation.md". Read `phases/execution.md` + `phases/audit-loop.md`. You are the ORCHESTRATOR — dispatch ALL code changes through the `ct-implementer` Agent (subagent_type "Coding Team Implementer"); NEVER hand-edit code yourself, any size (see [[no-direct-code-edits-phase5]] memory — user corrected this twice).

## Where the work lives
- **Worktree:** `/Users/cevin/src/codesight-mcp/.worktrees/audit-remediation`, branch `fix/audit-remediation-2026-07`, based on `origin/main` (tip `1ae7691`, carrying 6 of 8 Dependabot merges). Clean tree.
- **Venv is built** in the worktree — run tests with `.venv/bin/pytest --tb=short -q`, lint with `uvx ruff check <files>` (NOT `uv run --with ruff` — it mutates uv.lock).
- **Plan lives in MAIN repo:** `docs/plans/2026-07-15-audit-remediation.md` (status: `in-progress` — do NOT re-flip).
- The main repo working tree has the user's dirty `.gitignore` (M) + untracked `TODO.md`/`docs/handoff/` — LEAVE UNTOUCHED, never commit them.

## Progress: Tasks 0 → 2 DONE (5 commits on branch)
```
739e9f4 fix: harden injection matcher — colon-phrase bypass, multi-word signatures, dedup telemetry (audit #6 fix round)
1a4a968 fix: word-boundary injection matcher + bounded rule-ID telemetry (audit #6)
ca34710 fix: declare machine-readable limit bounds; align prose to 100 (audit #3)
a87364c docs: clarify load_all_specs test docstring (0c audit finding)
4ec076d refactor: single canonical registry bootstrap via load_all_specs (audit #2)
```
- **Task 0** (Dependabot #41–48 on main): 6/8 merged via admin-bypass (user authorized). **#45 (pathspec) + #47 (pytest-asyncio) STUCK** — Dependabot never processed rebase/recreate (heads unchanged over 25+ min; app likely can't push post-admin-merge). Both trivial dev/runtime range-widenings, affect no remediation code. **Action at Task 10/completion:** flag to user for manual handling (or they land whenever Dependabot wakes; then rebase branch). CHANGELOG "8 Dependabot merges" should be adjusted to 6 (or 8 if the last 2 get merged first).
- **Task 0b** (worktree) DONE. **Task 0c** (`load_all_specs` registry bootstrap) DONE + audited (spec+simplify PASS), 34 specs. **Task 1** (limit bounds, 4 tools + invariant test) DONE — audit satisfied by the self-enforcing `test_limit_advertising` invariant + diff inspection.
- **Task 2** (injection matcher) DONE + FULL audit (spec+simplify+harden) + a fix round applied per a USER DECISION (below). Full suite **2496 passed, 16 skipped**; security suite **584 passed, 1 skipped**; ruff clean. The fix round (739e9f4) has NOT been independently re-audited — its changes are behavior-anchored with passing tests, so re-audit is optional/low-value, but note it.

## CRITICAL — Task 2 security design decision (user-made, see [[injection-filter-posture]] memory)
The injection phrase filter is a SECONDARY layer; the `<<<UNTRUSTED_CODE>>>` wrapper is primary. User chose:
- KEEP `override`/`important:`/`you are` corroborated-WEAK, keep bare `assistant` weak, keep `### ` dropped (rejected blanking benign docstrings).
- FIXED colon-phrase bypass (`system:evil` now caught) + added STRONG multi-word signatures (`override all prior directives` now caught) + deduped telemetry helpers + synced SECURITY.md.
- DEFERRED (pre-existing, out of scope): camelCase-glued bypass (`ignoreAllPriorInstructions`) — the old matcher missed it too. Note in final report; do NOT fix here.

## Remaining tasks (fixed order per plan) — Task 3 next
3. **Item 1** — shared index-age helper. Create `core/freshness.py` (full code in plan §Task 3 Step 1), refactor `verify.py:43-56` onto it (fail-closed on unknown/future; default `max_age_hours = INDEX_AGE_THRESHOLD_DAYS*24`), add `index_age_days`+`age_threshold_exceeded`+`git_head` to `list_repos` (both sidecar + full-index branches) + `_write_metadata_sidecar` git_head, aggregate staleness in `get_status` (counts only, NO repo names — trusted envelope). Model sonnet. **NOTE: verify.py loads the FULL index's `indexed_at` (not the sidecar).** get_status.py + verify.py already read (both clean). Task 3 touches index_store.py (overlaps Task 2) — run after Task 2, fine now.
4a. **Item 2 prereq** — set `untrusted=True` on 5 specs (get_file_tree, get_repo_outline, lint_index, list_repos, verify) + fixture-exercised invariant test. Uses `load_all_specs`. Overlaps Task 3 files (list_repos, verify) — run AFTER 3.
4b. **Item 2a** — `scripts/export_contract.py` + `contract/operations.json` + byte-compare drift test. AFTER 4a. (Deferred refinements in plan §"Deferred to Phase 5" #1-2: recursive schema export + granular path classification — per-task spec reviewer handles.)
5. **Item 7** — scoped mypy (3 files) + fix 7 errors + `typecheck` group + CI job. `uv lock` after pyproject change. Plan §"Deferred" #5: the `data` annotation must be `dict[str, object]`/TypedDict not `dict[str,list[float]]` — confirm real shape.
6. **Item 5** — `core/platform_check.py` POSIX check + server/CLI wiring + classifiers + README. Plan §"Deferred" #6: make it a pure `_is_posix(name)` helper (NO monkeypatch/mocks in the test).
7. **Item 9** — rmdir `{output_folder}/` cruft + `.gitignore` line + define `_bmad/tea/config.yaml` `output_folder: _bmad-output`. Plan §"Deferred" #7: RUN the BMAD resolver, don't just assert existence.
8. **Item 8 (partial)** — prune 4 stale local branches (`git branch -d` not -D per Deferred #8) + stale remotes.
9. **Item 4** — version bump pyproject → 0.6.0, CHANGELOG.md, `scripts/check_counts.py` + CI, update counts across README + 5 docs. Runs AFTER test-adding tasks. **RECOUNT tests** (plan said 2512; actual baseline was 2484 at 0c, now 2496 — recount live, don't trust the literal). Plan §"Deferred" #3: also byte-compare visible README badge/prose, not just the marker.
10. **Completion gate** — full suite + ruff + mypy + `uv sync --frozen` + contract/counts + no-user-content assert + push + green CI. Plan §"Deferred" #4: `uv sync --frozen --extra test --group typecheck` BEFORE check_counts/mypy.

## Phase 5 exit gates (ALL blocking, after Task 10) — this feature is Large tier
1. Full-suite test + ruff (fresh). 2. `ct-qa-reviewer` (Agent, Explore, sonnet) on the whole diff. 3. Doc-drift scan (`phases/doc-drift-scan.md`). 4. Post-exec Codex `review` (`phases/post-execution-review.md`). Then Phase 6 completion (4 options).

## Landmines / notes
- **codesight index is STALE for this worktree** (indexed from a different checkout — search-text returns 0 for present symbols). Per mcp-resilience/codesight-fallback: retry once, then use Grep/Read. Every agent has hit this — expected.
- **verification-stamp hook**: git-safety-guard blocks commits without a fresh `.harness-verified` stamp (30-min TTL). Implementers must run real tests+lint then commit — never `--no-verify`. Working as intended.
- Model tiers per plan: 0c/2/3/4a/4b/5/9/10 = sonnet; 1/6/7/8 = haiku.
- Per-task audit: concentrate full 3-auditor passes on security/structural tasks (done for 2); mechanical/invariant-locked tasks (1) right-sized down. 3/4a/4b touch trust boundaries + contracts → audit fully.
- Two memory files created this session: `no-direct-code-edits-phase5.md`, `injection-filter-posture.md` (indexed in MEMORY.md).
```
