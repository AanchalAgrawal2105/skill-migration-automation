# Team Roles — Four-Person, One-Hour Sprint

## Operating model

The team works in four parallel lanes with one integration owner. Names should be assigned in minute 0–2. Each artifact has exactly one directly responsible individual, even when another person reviews it.

| Role | Primary ownership | Deliverable by minute 30 | Deliverable by minute 50 |
|---|---|---|---|
| A — Integrator and contracts | Schemas, pipeline, runnable entrypoint, integration | Frozen contracts and pipeline skeleton | End-to-end run and release freeze |
| B — Repository and verification | Ingest, profile, verifier registry, subprocess runner | Real profile from demo repo | Real syntax/test result and rollback anchor |
| C — LLM migration engine | LLM adapter, plan, scope, transform, optional repair, pack | Mock/live typed plan and scoped transform | Per-file diff with failure handling |
| D — Experience and demo | UI/CLI presentation, reports, demo repo, rehearsal | Demo fixture and stage/results view | Reports, second goal, rehearsed script |

## Role A — Integrator and contracts

### Owns

- `app/schemas.py`
- `app/pipeline.py`
- `app/main.py` or the chosen CLI entrypoint
- Integration decisions and scope enforcement
- Final smoke test and release tag/commit if used

### First actions

1. Publish the exact Pydantic contracts and `run(...)` signatures.
2. Create all module stubs so teammates can implement without waiting.
3. Add a mock `MigrationRun` fixture and a pipeline that can pass it through stages.
4. Announce contract freeze no later than minute 8.

### Integration policy

- No schema changes after minute 8 unless Role A approves and updates all fixtures.
- Integrate a thin vertical slice by minute 30, even if some stages are mocked.
- Replace mocks one stage at a time; never wait until minute 50 for a large merge.
- At minute 50, reject new features and accept only demo-blocking fixes.

## Role B — Repository and verification

### Owns

- `app/stages/ingest.py`
- `app/stages/profile.py`
- `app/stages/verify.py`
- `app/verifiers.py`
- Minimal Git helpers needed to establish the rollback anchor

### Constraints

- Optimize for a local demo-repository path.
- Exclude `.git`, `.venv`, `node_modules`, `dist`, `build`, and binary/large files.
- Run commands with a timeout and capture output; do not use `shell=True` for goal- or model-provided commands.
- Only commands selected from repository metadata or the verifier registry are allowed.

### Handoff contract

By minute 20, give Role A a real `RepoProfile`. By minute 35, accept a transformed worktree and return a real `VerifyResult`.

## Role C — LLM migration engine

### Owns

- `app/llm.py`
- `app/stages/plan.py`
- `app/stages/scope.py`
- `app/stages/transform.py`
- `app/stages/repair.py` only if time remains
- `packs/`

### Constraints

- Every LLM response must map to a Pydantic model or be rejected.
- Transform one file per call.
- Include only relevant sites and pack excerpts.
- Do not write files inside the LLM adapter; return proposed content to the stage.
- Provide deterministic fixture responses for `DEMO_MODE` before attempting prompt polish.

### Handoff contract

By minute 20, return a typed `MigrationPlan` from mock or live mode. By minute 35, return at least one real `FileChange`, including a unified diff and rationale.

## Role D — Experience and demo

### Owns

- `ui/streamlit_app.py` or a readable CLI renderer
- `app/stages/report.py`
- `demo/sample-repo/`
- `tests/fixtures/`
- Demo script and final rehearsal

### Constraints

- Build against frozen fixtures first.
- Always show whether data came from live LLM mode or demo mode.
- Make the plan, diff, verification status, risks, and rollback anchor visible.
- Prepare two migrations that require no engine change.

### Handoff contract

By minute 15, provide a tiny repository whose initial tests fail or whose old API is detectable and whose migrated state has a deterministic passing test. By minute 40, provide a complete presentation path using fixtures or the live pipeline.

## Shared rules

- Communicate interfaces and blockers, not play-by-play.
- A blocker unresolved for three minutes uses the documented fallback.
- Do not refactor another role's module during the build; coordinate at its boundary.
- No new dependencies after minute 30 unless they resolve a demo blocker.
- Preserve logs and failed diffs. Never hide an error to make the demo appear green.
- Keep commits small if using branches; otherwise use a shared branch with clearly announced file ownership.

## Checkpoints

### Minute 8 — Contract freeze

Role A reads the schemas and signatures aloud. Each owner confirms they can produce their output without another schema change.

### Minute 20 — Artifact check

- A: pipeline runs with fixtures.
- B: real `RepoProfile` exists.
- C: typed plan exists in live or demo mode.
- D: demo repository and expected migration are ready.

### Minute 35 — Vertical slice

The real demo repository must pass through Profile → Plan → Transform → Verify. UI polish and reports may still use plain text.

### Minute 50 — Freeze

Stop feature work. Roles B and C remain available only for defects. Role D drives two rehearsals while Role A fixes integration issues.

## Questions to assign people

Answer these during minute 0–2:

- Who has the most experience with Pydantic/FastAPI? Assign Role A.
- Who is most comfortable with Git and safe subprocess execution? Assign Role B.
- Who has used structured LLM outputs? Assign Role C.
- Who can best narrate and operate the demo under pressure? Assign Role D.

If one person fits multiple roles, prioritize A first, then C, B, and D; use the remaining teammate to absorb D with fixture-driven UI work.
