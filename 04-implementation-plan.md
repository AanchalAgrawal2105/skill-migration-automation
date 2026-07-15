# Implementation Plan — Demo in 60 Minutes

## Delivery strategy

Build a thin, honest vertical slice before adding breadth. The integration target is a trusted local Python demo repository and one migrated file. Every stage uses the production-shaped contracts, so mocked components can be replaced without changing the UI or pipeline.

## Minute 0–5: Decide and bootstrap

Role A records answers to the four decisions in `00-product-brief.md`. Unless the team has already installed and tested Streamlit, use a CLI as the guaranteed interface. Unless GitHub credentials are already working, commit locally and produce a PR preview.

Create:

```text
app/
  __init__.py
  main.py
  pipeline.py
  schemas.py
  llm.py
  verifiers.py
  stages/
    __init__.py
    ingest.py
    profile.py
    plan.py
    scope.py
    transform.py
    verify.py
    report.py
packs/
demo/sample-repo/
tests/fixtures/
ui/
```

Use only dependencies already available when possible. The minimum likely set is Pydantic and PyYAML; OpenAI and Streamlit are conditional enhancements.

## Minute 5–8: Freeze contracts

Copy the specified Pydantic models into `app/schemas.py`. Preserve field names and enum literals. If using Pydantic v2, prefer `Field(default_factory=list)` for `MigrationRun.changes` to avoid a mutable default while preserving the contract's external shape.

Add internal-only structured models if necessary, for example:

```python
class TransformOutput(BaseModel):
    modified: str
    rationale: str
```

These do not alter inter-stage contracts.

Publish fixture JSON for profile, plan, scope, changes, verification, and reports. Role A announces “contracts frozen.”

## Minute 8–20: Parallel foundation

### Role A: pipeline

- Implement `run_migration(repo_path, goal, pack_path=None, demo_mode=False)`.
- Construct `MigrationRun` and call the core stages.
- Add a callback such as `on_stage(name, status, run)` for rendering.
- Wrap each stage with a concise error that retains prior artifacts.
- Implement `python -m app.main --repo ... --goal ... [--pack ...] [--demo-mode]`.

### Role B: ingest/profile

- Resolve and validate `repo_path`.
- Reject paths outside the expected demo/work root if appropriate.
- Create/read baseline Git SHA.
- Build a filtered relative file tree.
- Detect `.py`, parse simple `requirements.txt` pins, and identify tests.
- Set `syntax_cmd={"python": "python -m py_compile {file}"}` and `test_cmd="pytest -q"` only when supported by the repo.

### Role C: LLM interface and plan

- Define live and fixture adapters behind the same methods.
- Pass a compact serialized profile, the exact goal, and pack data.
- Validate the response as `MigrationPlan`.
- Never repair JSON with ad hoc substring extraction; retry once or fail.

### Role D: demo fixture and renderer

- Create a tiny Python repository with one source file and one focused test.
- Add an old migration pattern in source and a knowledge pack under `packs/`.
- Create a second simple migration, such as changing a deprecated model/config value, expressible through another goal/pack.
- Render fixture stage events, plan steps, unified diff, and pass/fail output.

## Minute 20–35: Complete the core quartet

### Scope

Implement line-aware literal search using pack markers and breaking-change patterns. Normalize every path, skip binary/large files, and return deduplicated paths. Assign risk from the pack; default uncertain hits to `review` rather than `auto`.

### Transform

For each file in scope:

- Gather only its `UsageSite` entries.
- Ask the adapter for full modified content and rationale.
- Calculate `difflib.unified_diff`.
- Write the candidate only after validation.
- Invoke the file syntax checker with a timeout.
- Populate `FileChange` truthfully.

For fixture mode, select a structured response based on a fixture identifier or the provided fixture file, not migration-specific `if old_api` branches in pipeline code.

### Verify

- Run build first only if it is safe and necessary for the fixture.
- Run tests from the profile.
- Treat missing verification commands as not verified, not passed. For the demo fixture, ensure a real syntax or test command exists.
- Combine results into `VerifyResult`; do not infer success from log text.

### Integration gate at minute 35

Execute the primary goal. Do not proceed to UI polish until all are true:

- profile contains real repository facts;
- plan validates;
- at least one real file is changed;
- diff is visible;
- a real command returns exit code 0;
- rollback SHA is shown.

If this gate fails, apply the cut order in `02-task-breakdown.md` immediately.

## Minute 35–45: Reports and presentation

Generate reports deterministically from the typed run to remove another LLM dependency:

- Migration docs: goal, plan summary, per-file rationale and verify status.
- Risk report: one Markdown row per usage site/file, including risk, kind, syntax status, and untested paths.
- Rollback plan: rollback SHA, branch deletion/revert guidance, and dependency/environment notes.

If Streamlit is already functional, expose inputs and update a stage status container. Otherwise keep the CLI and format sections cleanly. Do not implement FastAPI merely to place it between a local UI and local pipeline during this hour.

## Minute 45–50: Prove genericity

Restore the controlled demo repository to its baseline through the prepared fixture workflow or use a fresh copy. Run a second migration by changing only `goal` and/or `pack_path`. Confirm that no code under `app/` changes.

Capture expected commands and outputs for the presenter:

```bash
python -m app.main --repo demo/sample-repo --goal "<primary goal>" --pack packs/<primary>.yaml
python -m app.main --repo demo/sample-repo --goal "<second goal>" --pack packs/<second>.yaml
```

Do not put real secrets in commands, fixtures, logs, screenshots, or reports.

## Minute 50–60: Freeze and rehearse

### Rehearsal 1

Run the primary path from a clean baseline. The presenter narrates:

1. Input is a goal and optional pack.
2. Profile facts are deterministic.
3. Plan and isolated edit are model-produced or clearly labeled fixtures.
4. Diff is inspectable.
5. Tests, not the LLM, decide success.
6. Rollback anchor makes the original state recoverable.

Time the run and record any manual correction. Fix only blockers.

### Rehearsal 2

Run the second migration and emphasize that only data changed. Exercise the fallback once so the presenter knows how to switch to `DEMO_MODE` without pretending it is live.

### Freeze criteria

- Two consecutive clean demo runs or one live plus one explicit fallback run.
- No uncommitted accidental edits outside the demo worktree.
- One copy/paste primary command.
- Verification output visible and truthful.
- Presenter can explain deferred production security work.

## Implementation guardrails

### No hardcoded migration logic

Allowed:

- generic pack field interpretation;
- literal search for patterns supplied by a pack/LLM;
- fixtures keyed by fixture filenames in explicit demo mode.

Not allowed:

- pipeline branches for “OpenAI v0,” “Python 2,” or any named migration;
- demo API strings embedded in transform/profile/verify modules;
- verifier success determined by the goal text.

### Deterministic verification

- Use exit codes and timeouts.
- Keep command selection separate from model output.
- Treat no tests as an explicit coverage risk.
- Never create a success/PR result when `verify.passed` is false.

### Safe file handling

- Resolve paths and enforce repository containment.
- Ignore symlinks that escape the root.
- Bound file size and skip binary data.
- Keep originals until syntax and test results are recorded.
- Never automatically run destructive rollback commands.

## Post-hour backlog

1. Docker/Firecracker-style isolated execution for arbitrary repositories.
2. Remote clone and safe ZIP extraction.
3. FastAPI job API, persistence, and event streaming.
4. Bounded LLM repair with per-file retry accounting.
5. Additional language profilers and verifier adapters.
6. GitHub App authentication and human-approved PR creation.
7. Evaluation suite covering scope precision, unrelated-edit rate, compile rate, test pass rate, latency, and cost.

## Final go/no-go questions

At minute 50, the team lead asks:

- Does the run execute real syntax/tests, or is verification mocked? If mocked, it is a no-go until a real command is wired.
- Can the presenter reset or recreate the demo repository reliably? If not, use disposable copies.
- Is live LLM behavior stable across two runs? If not, use and disclose `DEMO_MODE`.
- Does any output expose a token or local secret? If yes, stop and redact before presenting.
- Can a second migration run without changes under `app/`? If not, do not claim genericity.

The demo is ready only when these answers are: real verification, reliable reset, stable or disclosed fallback, no secret exposure, and no engine change.
