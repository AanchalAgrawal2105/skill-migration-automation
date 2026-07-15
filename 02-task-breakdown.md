# One-Hour Task Breakdown

## Critical path

The critical path is:

`contracts → real profile → typed plan → one-file transform → deterministic verify → demo rehearsal`

Everything else is optional until this path works.

## Minute-by-minute schedule

| Time | Role A — Integrator | Role B — Repo/verify | Role C — LLM engine | Role D — Surface/demo | Exit condition |
|---|---|---|---|---|---|
| 00–03 | Assign roles; decide CLI/UI, live/mock LLM, PR preview | Confirm local tools | Confirm API/model access | Confirm demo story | Defaults recorded |
| 03–08 | Create structure; freeze schemas/signatures | Stub ingest/profile/verify | Stub LLM/plan/scope/transform | Create demo repo and fixtures | Imports succeed |
| 08–15 | Wire fixture-only pipeline | Build file tree, language and manifest detection | Build structured plan and transform fixtures | Add test that distinguishes old/new state | Fixture pipeline runs |
| 15–20 | Integrate real profile | Return `RepoProfile` with rollback SHA | Return typed plan in live or demo mode | Render stage state in CLI/UI | Profile + plan visible |
| 20–30 | Wire stage errors and state updates | Implement timeout runner and verify | Implement pack-based scope and per-file edit | Prepare report templates and second goal | One file changes |
| 30–35 | Drive first vertical-slice run | Fix command detection | Fix prompt/output parsing | Verify demo fixture expectations | Core quartet completes |
| 35–40 | Stabilize interface | Improve failed-file/log reporting | Add one syntax retry only if stable | Connect UI to real pipeline | Real results displayed |
| 40–45 | Add concise run summary | Add safe log truncation | Add explicit manual fallback | Generate risk/rollback/docs | Credible handoff artifacts |
| 45–50 | Run second goal; remove blockers | Support rehearsal | Support rehearsal | Lead first rehearsal | Two goals demonstrated |
| 50–57 | Freeze; fix only blockers | Fix only blockers | Fix only blockers | Lead second rehearsal | Clean run completed |
| 57–60 | Package command and README note | Stand by | Stand by | Present | Demo-ready |

## Work packages

### WP-1: Contracts and skeleton — Role A — 5 minutes

Deliver:

- Frozen models from the implementation spec.
- Stage signature convention: `run(run: MigrationRun, ...) -> MigrationRun`.
- Importable modules for the four core stages.
- Fixtures for a complete successful `MigrationRun`.

Done when a fixture-only command prints the plan, one diff, and a passing verification result.

### WP-2: Local ingest and profile — Role B — 12 minutes

Deliver:

- Accept an existing local path.
- Initialize Git and commit only for the controlled demo repository when no commit exists.
- Record `rollback_anchor` before mutation.
- Walk a filtered file tree.
- Detect Python, `requirements.txt`/`pyproject.toml`, dependencies, and `pytest -q`.
- Populate the registry-based syntax command.

Done when the demo repository produces a valid `RepoProfile` with a real SHA and expected dependency.

### WP-3: Typed plan — Role C — 10 minutes

Deliver:

- An LLM adapter with a live implementation and explicit fixture fallback.
- A small prompt containing goal, profile summary, and optional pack.
- Validation into `MigrationPlan`.

Done when malformed output fails clearly and a valid response produces ordered, risk-labeled steps.

### WP-4: Scope and transform — Role C — 15 minutes

Deliver:

- Load YAML pack as data.
- Search `detect.markers` and `breaking_changes.pattern` with literal matching.
- Deduplicate `files_to_change`.
- Transform exactly one file per call, validate full modified content, compute a unified diff, and attach rationale.
- Run the file's syntax command after writing; on failure, restore the original or mark manual.

Done when at least one demo file has a non-empty, focused diff and unrelated text remains unchanged.

### WP-5: Deterministic verify — Role B — 15 minutes

Deliver:

- Select build/test commands from the frozen profile only.
- Run in the repository root with a 60-second timeout.
- Capture return codes and truncate logs to a safe display size.
- Return a truthful `VerifyResult`.

Done when changing the test fixture can produce both a real pass and a real fail.

### WP-6: Surface and reports — Role D — 20 minutes

Deliver:

- A CLI renderer first; Streamlit is an enhancement.
- Visible stage status, plan, diff, verification result, and mode label.
- Deterministic Markdown migration docs, risk table, and rollback steps assembled from structured artifacts.

Done when an observer can explain what changed, whether it passed, what is risky, and how to return to the original SHA.

### WP-7: Integration and rehearsal — Roles A and D — 15 minutes

Deliver:

- A single copy/paste run command.
- Primary migration run without manual edits.
- Second migration with only the goal/pack changed.
- Failure fallback: fixture mode and saved expected output.

Done after two consecutive runs complete within the allotted demo time.

## Dependency map

| Consumer | Needs | Available by |
|---|---|---:|
| Profile | Demo repository | minute 10 |
| Plan | Frozen schemas + profile | minute 20 |
| Transform | Schemas + scope sites + demo file | minute 25 |
| Verify | Profile commands + transformed worktree | minute 35 |
| UI/reports | Fixtures initially; real `MigrationRun` later | minute 8 / 40 |

## Test checklist

### Contract tests

- Fixture JSON validates against each Pydantic model.
- Invalid risk and change-kind values are rejected.
- `MigrationRun` serializes for UI use.

### Profile tests

- Vendored directories are excluded.
- Python and the demo dependency are detected.
- Rollback SHA exists.

### Transform tests

- Diff is non-empty for a changed file.
- No file outside `files_to_change` is written.
- Syntax failure sets `syntax_ok=false` and `kind=manual`.

### Verification tests

- A passing command returns `passed=true`.
- A failing or timed-out command returns `passed=false` with a bounded log.
- No later stage describes a failed run as committed or ready to merge.

### Genericity test

- Run goal/pack A, reset to rollback anchor, then run goal/pack B.
- Confirm no application source changes are needed between the two runs.

## Cut order at time pressure

At each missed checkpoint, cut from the top of this list and continue:

1. Streamlit; retain CLI output.
2. Repair loop; mark failures manual.
3. Generated narrative reports; use deterministic templates.
4. Remote clone and PR integration; retain local path and PR preview.
5. Multiple files; migrate one representative file.
6. Live LLM; switch to clearly labeled structured fixtures.

Never cut real profile inspection, a real file diff, or real deterministic verification.
