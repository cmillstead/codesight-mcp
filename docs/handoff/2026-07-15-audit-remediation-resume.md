# Handoff — Audit Remediation Phase 5 (resume)

**Written:** 2026-07-15 (session mid-Phase-5, before a `/clear`)
**Skill:** `/coding-team` Phase 5 execution
**Plan:** `/Users/cevin/src/codesight-mcp/docs/plans/2026-07-15-audit-remediation.md` (gitignored — main repo only, not in the worktree)

## Resume command
`/coding-team` → `resume Phase 5, plan docs/plans/2026-07-15-audit-remediation.md`

## Where the work lives
- **Worktree:** `/Users/cevin/src/codesight-mcp/.worktrees/audit-remediation`
- **Branch:** `fix/audit-remediation-2026-07` (off `origin/main`, which already carries Task 0's Dependabot merges)
- **ALL execution happens in the worktree.** The user's main-repo working tree is intentionally left dirty (`.gitignore` M, `TODO.md`) — do NOT touch it.
- Tests: `.venv/bin/pytest --tb=short -q` (project venv). Lint (authoritative): `uv run --with ruff ruff check <files>` (local `ruff` shim prints a non-standard format).

## FIRST STEP ON RESUME
Run `git -C .worktrees/audit-remediation log --oneline origin/main..HEAD` and match commits to the checklist below to find the true next task. **A Task 6 implementer was in-flight at handoff** — if you see a commit `feat: centralized POSIX startup check ... (audit #5)`, Task 6 is DONE → audit it / continue at Task 7. If absent, Task 6 must be (re-)run.

## Tasks DONE (committed, audit-clean, independently verified)
| Task | What | Commit(s) |
|---|---|---|
| 0 | Dependabot #41–48 merged | on origin/main |
| 0b | worktree setup | — |
| 0c | registry bootstrap `load_all_specs` | `4ec076d`, `a87364c` |
| 1 | machine-readable `limit` bounds | `ca34710` |
| 2 | injection matcher + telemetry | `1a4a968`, `739e9f4` |
| 3 | shared freshness helper + staleness surface | `c27cbb8`, `6d83e44` |
| 4a | trust-flag reconciliation (5 tools untrusted=True) + invariant test + **Finding A** | `f2a5f94`, `169f987`, `3d4a6f8` |
| 4b | operation contract export + byte-compare drift test | `6d0819f` |
| 5 | scoped mypy in CI (typecheck group) + 9 type fixes | `5e0e167` |

**Full suite green at handoff: 2531 passed, 16 skipped.** Baseline this feature is at HEAD `5e0e167` (+ possibly the Task 6 commit).

### Finding A (important — a NEW HIGH we added, user-approved)
The harden same-class sweep on Task 4a found `index_repo`/`index_folder` echoed attacker-controlled filenames with no trust framing. **User chose "fix now."** Fixed across 3 audit rounds: 3-layer `list_repos` pattern (`untrusted=True` on both specs, `make_meta(source="index", trusted=False)` + `wrap_untrusted_content` on filenames AND the `repo` field, in `_indexing_common.finalize_index` + `index_folder` incremental branch). Recorded here so it's not lost; fold into the CHANGELOG (Task 9) and completion summary.

## Tasks REMAINING (in order)
- **Task 6 — POSIX startup check** (in-flight at handoff). New `core/platform_check.py` + wire `ensure_posix()` into `server.py` `main()` + `_run_cli_tool()`; pyproject classifiers; README platform note + correct stale wrapper path `~/.claude/servers/codesight/mcp-server.ts` → `~/src/codesight-plugin/mcp-server.ts`. **Deferred refinement #6: NO mocks** — pure `_is_posix(name)`/`_require_posix(name)` helpers testable with literal `"posix"`/`"nt"`, NOT `monkeypatch.setattr(os,"name",...)`. Keep the fcntl guard in `locking.py`. Model: sonnet.
- **Task 7 — remove `{output_folder}/` cruft.** `find '{output_folder}' -type f` (expect empty) then `rmdir` (NOT `rm -rf`); add `{output_folder}/` to `.gitignore` (stage ONLY that one line — do not restage the user's separate .gitignore edits; the worktree is clean so this is automatic); define `output_folder: _bmad-output` in `_bmad/tea/config.yaml`. **Deferred #7: RUN the BMAD resolver/templating to PROVE `{output_folder}` resolves to `_bmad-output`, don't just assert `_bmad-output/` exists.** Model: haiku.
- **Task 8 — prune stale branches.** Delete 4 local branches with `git branch -d` (merge-safe, NOT `-D`): `feat/05-01-language-depth-imports-calls`, `feat/batch6-languages`, `feat/language-expansion-batch5`, `feat/phase04-01-web-config-languages`. Prune stale remotes (>14d, no open PR) — cross-check `gh pr list` + `git branch -r --merged origin/main` first; report uncertain ones rather than force-delete. pip-audit gating is DEFERRED (NOT in scope). Model: haiku.
- **Task 9 — version + CHANGELOG + counts (runs LAST among code tasks).** `scripts/check_counts.py` (registry bootstrap, `pytest --collect-only` exit 0, precise generated marker); `pyproject.toml` version `0.1.0`→`0.6.0`; create `CHANGELOG.md` (Keep a Changelog) covering the v0.6.0 milestone + this audit remediation (incl. Finding A); update EVERY count occurrence across README + `docs/{index,project-overview,architecture,development-guide,source-tree-analysis}.md`; add `check_counts` to CI `lint` job (install frozen test extra first). **RECOUNT tests after all test-adding tasks — baseline is now ~2531+, README badge is stale at `tests-2495`. Deferred #3: also byte-compare/regex the VISIBLE README badge/prose, not just the denylist.** Model: sonnet.
- **Task 10 — completion gate.** Deferred #4: start with `uv sync --frozen --extra test --group typecheck` BEFORE check_counts/mypy. Full suite + `uv run --with ruff ruff check .` + `uv run --group typecheck mypy` + `uv sync --frozen` + contract diff (`python scripts/export_contract.py | diff - contract/operations.json`) + `check_counts.py`. Assert NO user content leaked: `git diff origin/main...HEAD -- TODO.md` empty; only `.gitignore` change is the one `{output_folder}/` line. Push `fix/audit-remediation-2026-07`, open PR, watch CI green (lint incl. counts, test shards, **typecheck** — the mypy CI job's green is only verifiable at push). Model: sonnet.

## After Task 10: Phase 5 exit gates + Phase 6
Per `phases/execution.md`: (1) effective-tier recompute, (2) **feature-level QA reviewer** on the full diff (`git diff origin/main..HEAD`), (3) doc-drift scan (`phases/doc-drift-scan.md`), (4) **post-exec Codex review** (`phases/post-execution-review.md`) — this feature is Medium/Large so all RUN. Then Phase 6 completion (`phases/completion.md`): 4 options, flip plan frontmatter `status: in-progress`→`complete`, learning loop.

## Per-task process (each remaining task)
Implementer (Coding Team Implementer) → completeness check → audit (spec + simplify + harden as warranted; harden for anything touching trust/security/defensive code; skip harden for pure build-tooling/docs) → triage/fix rounds (max 3) → independent verify → commit. Reap each subagent (`TaskStop` by name) once its report is in hand. Auditors go idle WITHOUT auto-sending findings — you must SendMessage to request their report.

## Known issues / notes (carry into completion summary)
- **codesight MCP is DEGRADED this whole session** (stale index for the worktree / wrapper invocation errors). Per mcp-resilience: one retry then fall back to Read/git. Do NOT keep retrying it.
- **`.harness/hooks/pre-commit-verify.sh`** prints noisy `grep: repetition-operator operand invalid` errors + an env-var dump on commit (pre-existing hook bug, likely a bad regex in a secret-scanner). Non-blocking — commits succeed after re-running pytest+ruff and touching `.harness-verified`. It's harness infra; a product-repo-rooted session should NOT edit it — flag to the user.
- **Pre-existing mock:** `tests/tools/test_diff_aware_indexing.py` mocks git subprocess and now carries a hook-sanctioned `# mock-ok:` annotation (added to unblock a Task-4a edit). Arguably violates no-mocks; out of scope — flag to user for a possible real-git-subprocess rewrite later.
- **PyPI placeholder registration** for `codesight-mcp` still a TODO (from memory index) — not in this plan.

## NOT in scope (do not do)
Item 10 (split `parser/languages.py`) — user-deferred. pip-audit gating (36 open vulns). Physical relocation/monorepo of codesight-plugin. Cross-repo parity in codesight-plugin's CI. Broadening mypy beyond the 3 files. Re-indexing the codesight self-index.
