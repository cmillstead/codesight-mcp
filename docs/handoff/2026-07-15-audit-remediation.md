# Handoff — audit-remediation (coding-team)

**Written 2026-07-15, end of Phase 4. Next session resumes at Phase 5.**

## Where we are
- `/coding-team` run remediating the 2026-07-02 audit (`~/Documents/obsidian-vault/AI/context/goals/projects/fable-upgrades/audits/2026-07-02/codesight-mcp.md`).
- **Phase 4 COMPLETE.** Plan: `docs/plans/2026-07-15-audit-remediation.md` (status: planned), 15 tasks, traceability 7 fixed / 2 partial / 1 deferred.
- Plan-doc reviewer APPROVED. Codex plan gate ran **2 rounds, both REVISE** (22 findings, all verified real). User ACCEPTED after a scoped must-fix pass (A–F). 8 refinements are recorded in the plan's **"## Deferred to Phase 5 (Codex round-2 residuals)"** section — the per-task spec-reviewer + post-exec Codex gate handle them during execution.

## Locked user decisions (do NOT re-litigate)
1. **Item 2 (TS wrapper):** contract-snapshot only. Wrapper lives in a SEPARATE repo `~/src/codesight-plugin` (NOT `~/.claude/servers/codesight/`, which doesn't exist). No physical move. Cross-repo parity is a follow-up in that repo.
2. **Item 3 (scan_security limit):** document 100 (don't raise the clamp).
3. **Item 6 (injection blocklist):** word-boundary/corroborated MATCHER rewrite, NOT phrase deletion (existing security tests require the phrases). Only `### ` dropped.
4. **Item 8 (pip-audit gating):** DEFERRED to its own milestone — 36 pre-existing vulns across 10 packages. Task 8 keeps only branch pruning.
5. **Item 10 (split languages.py):** DEFERRED to its own milestone.

## Phase 5 entry steps
1. Create the clean worktree (Task 0b): `git fetch origin && git worktree add .worktrees/audit-remediation -b fix/audit-remediation-2026-07 origin/main`. Leaves the user's dirty `.gitignore`/`TODO.md` untouched — do NOT commit those.
2. Flip plan frontmatter `status: planned` → `in-progress` before first implementer dispatch.
3. Fixed task order: 0 (Dependabot #41–48 on main) → 0b (worktree) → 0c (registry bootstrap `load_all_specs`) → 1 → 2 → 3 → 4a → 4b → 5 → 6 → 7 → 8 → 9 → 10 (completion gate).
4. Phase 5 exit gates (all 4 blocking): full `.venv/bin/pytest --tb=short -q` + ruff, ct-qa-reviewer, doc-drift scan, post-exec Codex review.

## Notes
- Tests via `.venv/bin/pytest` only; `uv lock` after any dependency change.
- The two prior-session agents (planning-worker, plan-doc-reviewer) are gone after /clear — respawn fresh for Phase 5.
- Language constant is `LANGUAGE_REGISTRY` (not `SUPPORTED_LANGUAGES`). Real test count is 2,512.
