---
name: Operation contract sync via snapshot, not monorepo
description: Keep the TS dispatch wrapper a separate repo; enforce engine↔wrapper parity with an exported contract file + byte-compare drift test rather than vendoring or a monorepo
type: project
---

## Context
The 2026-07-02 audit's item 2 ("bring the dispatch wrapper into the repo / integration-test it") assumed the wrapper was loose, unversioned files at `~/.claude/servers/codesight/`. That premise was false: the wrapper is `~/src/codesight-plugin`, an already-versioned Claude Code plugin with its own two-tier CI (hermetic typecheck/manifest + integration clone-and-index against the engine pinned at a commit). The real remaining risk was narrower: nothing guaranteed the wrapper's operation set + trust flags stayed in sync with the Python `ToolSpec` registry (drifts observed: TS modeled only `untrusted` not `destructive`; TS advertised `.max(500)` while the engine clamps `limit` to 100; 5 tools had `untrusted` flag/`_meta` mismatches).

## Decision
Enforce parity via a **contract snapshot**: `scripts/export_contract.py` exports the live registry (op name, untrusted/destructive/index_gate, required_args, ci_exit_key, normalized param schemas incl. path classes) to `contract/operations.json`, guarded by a byte-compare drift test (`test_operation_contract.py`). The 5-tool trust flags were reconciled to their real `_meta` (fixture-exercised invariant test) BEFORE export so the snapshot canonizes correct flags. The cross-repo consumer step (codesight-plugin reading `contract/operations.json` + adding a `destructive` flag) is a follow-up **in that repo**, out of scope here.

## Alternatives Considered
- **Git-subtree monorepo** — rejected: collapses two independently-versioned, independently-CI'd artifacts; heavy for a single-maintainer OSS project.
- **Literal vendor + deploy script (abandon the plugin repo)** — rejected: throws away the wrapper's existing version control + CI for a worse deployment story.

## Constraints
- The wrapper repo pins the engine to a specific commit; the engine must not assume the wrapper updates in lockstep.
- `get_status` and other trusted envelopes must stay counts-only (no attacker-influenceable repo-name strings) — the contract export must not leak such data.

## Consequences
If reversed (e.g. someone vendors the wrapper or merges the repos) without understanding why: you lose the two independent CI signals, and the byte-compare drift test — the actual guarantee that engine and wrapper agree — becomes meaningless because there's no separate consumer to drift from. The snapshot only has value while the wrapper is a distinct consumer of `contract/operations.json`.
