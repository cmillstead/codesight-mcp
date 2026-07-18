# Handoff — Audit Remediation Phase 5 EXIT GATES (resume)

**Written:** 2026-07-15, mid-Phase-5-exit-gates, right before a `/clear` (Codex review was about to run).
**Skill:** `/coding-team` Phase 5 → exit gates → Phase 6.
**Plan:** `/Users/cevin/src/codesight-mcp/docs/plans/2026-07-15-audit-remediation.md` (gitignored; main repo only). Frontmatter still `status: in-progress`. A `## Completion Checklist` with `- [ ] Second-opinion review` was appended at the end (needed by /second-opinion + /release).

## Resume command
`/coding-team` → `resume Phase 5, plan docs/plans/2026-07-15-audit-remediation.md`

## Where work lives
- **Worktree:** `/Users/cevin/src/codesight-mcp/.worktrees/audit-remediation`, branch `fix/audit-remediation-2026-07` (off `origin/main`). **17 commits ahead.** Tree CLEAN.
- ALL execution happens in the worktree. User's main tree is intentionally left dirty (`.gitignore` M, `TODO.md`) — do NOT touch it.
- Tests: `.venv/bin/pytest --tb=short -q`. Lint: `uv run --with ruff ruff check .`. Types: `uv run --group typecheck mypy`.
- **codesight MCP is DEGRADED this whole session** — use Grep/Read, one retry max then fall back (mcp-resilience).
- Note: a git-output wrapper reformats `git status`/`--short` to terse strings ("ok", "clean — nothing to commit", "ahead N"). Use `git log --oneline | cat` and `git diff --stat` for ground truth.

## DONE — all plan tasks 0c–9 committed + Task 8 branch prune
| Task | What | Commit(s) |
|---|---|---|
| 0 | Dependabot — PARTIAL (see caveat) | on origin/main |
| 0c | registry bootstrap `load_all_specs` | 4ec076d, a87364c |
| 1 | machine-readable `limit` bounds | ca34710 |
| 2 | injection matcher + telemetry | 1a4a968, 739e9f4 |
| 3 | shared freshness helper + staleness surface | c27cbb8, 6d83e44 |
| 4a | trust-flag reconciliation + Finding A | f2a5f94, 169f987, 3d4a6f8 |
| 4b | operation contract export + drift test | 6d0819f |
| 5 | scoped mypy in CI (typecheck group) | 5e0e167 |
| 6 | POSIX startup check | 2aba361 |
| 7 | BMAD output_folder + gitignore cruft | b1250e0 |
| 8 | branch prune (4 local + 15 merged remotes deleted; NO commit) | — |
| 9 | version 0.6.0 + CHANGELOG + counts | d8b0d4f |
| QA fix | get_dead_code clamp→100 + docstring, get_repo_outline exemption comment, real clamp test | 1c4b157 |
| doc-drift fix | 6 structural-doc MUST_FIX | d306d2c |

## Phase 5 EXIT GATES — status
1. **Full-suite verification: GREEN** (independently, twice). 2536 passed / 16 skipped; ruff clean; mypy `Success` (3 files); `check_counts` → `ops=34 langs=66 tests=2550` exit 0; contract export byte-identical (no drift); `uv lock --check` current.
2. **Effective tier: LARGE** (53 files, +3080/−135; RISK high — injection matcher + trust boundaries). All gates RUN.
3. **QA reviewer: PASS_WITH_CONCERNS** — all findings triaged + FIXED in 1c4b157: (Finding 1 HIGH was verified NOT a behavioral bug — global `_INT_PARAM_BOUNDS["limit"]=(1,100)` in `server._sanitize_arguments` clamps every tool's limit to 100 in BOTH dispatch paths before the handler, so `get_dead_code`'s local 500 was shadowed; fixed docstring + aligned `_MAX_DEAD_CODE`→100 + added real clamp test. Finding 3 LOW = justified inconsistency, documented get_repo_outline's sanitized-repo exemption with a comment.) 0 dark features.
4. **Doc-drift: 6 MUST_FIX fixed** (d306d2c) — new core modules + scripts/contract dirs + typecheck job added to structural docs. Verified clean: wrapper path, POSIX note, SECURITY.md matcher desc, CHANGELOG.
5. **Post-exec Codex review: IN PROGRESS.** User chose **BOTH** (review + challenge). Pre-flight DONE & clean (audit line: applicable 24 all ✓, dismissed 6 scope-mismatch, total 30). The `codex review --base origin/main` command was interrupted by the /clear — NOT yet run.

## NEXT STEPS ON RESUME (in order)
1. **Run Codex `review` then `challenge`** (user already chose "both") from the worktree: `codex review --base origin/main 2>&1 | tee <scratch>/so-review.txt`, then challenge mode per `skills/second-opinion/reference.md`. Pre-flight is already clean — no need to redo it. Address any P1/P2 findings (fix → re-verify GREEN → re-dispatch). Then mark the plan: `- [x] Second-opinion review (challenge: <one-line>)`.
2. **Phase 6 completion** (`phases/completion.md`): present 4 options; flip plan frontmatter `status: in-progress`→`complete`; Agent Teardown; learning loop. Task 10 = push `fix/audit-remediation-2026-07`, open PR, watch CI GREEN (lint incl. counts, 4 test shards, typecheck). Assert no user content leaked: `git diff origin/main...HEAD -- TODO.md` empty; only `.gitignore` change is the one `{output_folder}/` line.

## Carry into completion summary / flag to user
- **Empty `{output_folder}/` cruft dir still physically in the USER'S MAIN tree** (`/Users/cevin/src/codesight-mcp/{output_folder}/test-artifacts`, untracked, EMPTY). Worktree design doesn't reach it. Shipped fix (gitignore + `output_folder: _bmad-output` key) prevents recurrence. OFFER to `rmdir '{output_folder}/test-artifacts' '{output_folder}'` in the main tree.
- **Dependabot caveat (Task 0 was PARTIAL):** pytest #46 + pytest-cov #48 merged; setup-uv v8 #41 / upload-artifact #42 / retry #43 applied on main; **#45 pathspec + #47 pytest-asyncio STILL OPEN.** CHANGELOG records this accurately (not "8 merged").
- **check_counts uses `--collect-only`=2550; a full run collects 2552** (2 runtime-generated tests). Benign — gate is CI-stable under Python 3.12 (local venv IS 3.12.9; collection not version-dependent). Docs MUST advertise 2550 (the collect-only number) or the gate reds.
- **NICE_TO_HAVE docs → `/doc-sync` after merge:** get_status staleness fields + list_repos new fields undocumented; POSIX note missing from dev-guide Prerequisites; consider new ADR `docs/decisions/006-posix-only-platform.md`; add CHANGELOG.md to docs/index.md "Existing Documentation" list.
- **Pre-existing (out of scope, flag only):** per-category test-count breakdowns in architecture.md/development-guide.md/source-tree-analysis.md are internally inconsistent with the total (not caught by the total-count gate). Pre-existing mock in `tests/tools/test_diff_aware_indexing.py` (`# mock-ok:` annotation) — possible real-git rewrite later. `.harness/hooks/pre-commit-verify.sh` prints noisy `grep: repetition-operator invalid` on commit (harness infra bug — a product-repo session should NOT edit it; flag to user).

## NOT in scope
Item 10 (split parser/languages.py) — user-deferred. pip-audit gating (36 vulns). Physical relocation/monorepo of codesight-plugin. Cross-repo parity in codesight-plugin CI. Broadening mypy beyond 3 files. Re-indexing the self-index.
