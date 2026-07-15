# Architecture — One-Hour MVP

## System boundary

The MVP is a local application operating on a controlled repository path. It accepts:

- `repo_path`: local source repository
- `goal`: plain-English migration objective
- `pack_path`: optional YAML knowledge pack
- `demo_mode`: explicit switch for structured fixture responses

It produces a `MigrationRun`, modified files on a migration branch or disposable copy, verifier logs, Markdown reports, and a rollback anchor. Network cloning, GitHub PR creation, and untrusted-repository isolation are outside the one-hour boundary.

## Component flow

```text
CLI / minimal Streamlit
        |
        v
Pipeline orchestrator ───────────────────────────────┐
        |                                             |
        v                                             |
  1. Ingest/Profile ──> RepoProfile                  |
        |                                             |
        v                                             |
  2. Plan ────────────> MigrationPlan   <── LLM adapter / fixtures
        |                                             |
        v                                             |
  3. Scope ───────────> ScopeResult     <── goal + optional YAML pack
        |                                             |
        v                                             |
  4. Transform ───────> FileChange[]    <── one scoped file per call
        |                                             |
        v                                             |
  5. Verify ──────────> VerifyResult    <── bounded subprocess runner
        |                                             |
        v                                             |
  6. Report ──────────> Reports + PR preview ─────────┘
```

The public demo emphasizes stages Profile, Plan, Transform, and Verify. Ingest is folded into Profile for speed; Scope supports Transform; Report is a deterministic presentation layer.

## Data contracts

`app/schemas.py` is the integration boundary and must use the models supplied in the implementation spec without renaming fields. Each stage updates its corresponding field on `MigrationRun` and returns the run.

Recommended signatures:

```python
def profile(run: MigrationRun, repo_path: Path) -> MigrationRun: ...
def plan(run: MigrationRun, goal: str, pack: dict | None, llm: LLM) -> MigrationRun: ...
def scope(run: MigrationRun, goal: str, pack: dict | None) -> MigrationRun: ...
def transform(run: MigrationRun, pack: dict | None, llm: LLM) -> MigrationRun: ...
def verify(run: MigrationRun, runner: CommandRunner) -> MigrationRun: ...
def report(run: MigrationRun) -> MigrationRun: ...
```

The pipeline owns sequencing and error boundaries. Stages do not import or call later stages.

## Core components

### Orchestrator

Responsibilities:

- Validate inputs.
- Create one `MigrationRun`.
- Call stages in order.
- Emit stage events for CLI/UI display.
- Stop mutation when a required stage fails.
- Preserve partial artifacts for inspection.

For the MVP, a Python generator or callback is sufficient for stage events. A queue, database, background worker, or WebSocket is unnecessary.

### Repository profiler

Uses deterministic filesystem and manifest inspection only. It filters known generated/vendor directories, detects language by extension, reads a bounded set of supported manifests, and selects commands from the verifier registry or explicit repository metadata.

The MVP implements Python fully. Other registry entries show the generic extension point but need not be exercised.

### LLM adapter

Exposes narrow methods instead of a general chat interface:

```python
class LLM:
    def create_plan(...) -> MigrationPlan: ...
    def transform_file(...) -> TransformOutput: ...
```

Live mode uses the current configured model through the OpenAI SDK and validates structured output. Demo mode loads checked-in JSON fixtures with the same return types. The UI must label the active mode.

Model IDs belong in environment configuration, not source constants tied to a particular migration. Model availability must be confirmed during setup; the architecture does not require a specific model name.

### Knowledge-pack loader

Loads YAML and passes it verbatim or as bounded relevant excerpts into plan and transform. Pipeline behavior must not branch on a pack name. Generic code may interpret common fields such as `detect.markers`, `breaking_changes[].pattern`, `fix`, and `risk`.

### Scope engine

In the one-hour MVP, pack-assisted scope uses literal, line-aware search over text files. Without a pack, the LLM may return candidate literals, but the filesystem search remains deterministic. Each hit becomes a `UsageSite` and each path is normalized and checked to remain inside the repository root.

### Transform engine

For each scoped file:

1. Read and retain the original content.
2. Send only that file, its sites, the goal, and relevant pack data.
3. Validate a full replacement plus rationale.
4. Reject an unchanged response when a change was expected.
5. Write the candidate, calculate a unified diff, and run syntax verification.
6. If syntax fails, restore or mark the file manual; never silently keep a broken candidate as successful.

One-file isolation limits prompt size and makes failures attributable.

### Command runner and verifier

The runner executes only commands selected from trusted registry/repository configuration, inside the repository root, with:

- argument lists where practical;
- no interpolation from the migration goal or model response;
- a 60-second timeout;
- captured stdout/stderr and return code;
- bounded output for display;
- process termination on timeout.

This local subprocess design is acceptable only for the controlled hackathon fixture. Running arbitrary uploaded repositories requires a container or stronger sandbox and is deferred.

## State and rollback

Before transformation:

1. Confirm the repository has a clean controlled baseline.
2. Initialize Git and make a baseline commit if the demo fixture is not already committed.
3. Store the original `HEAD` in `rollback_anchor`.
4. Create a `migrate/<goal-slug>` branch if time permits; otherwise work in a disposable copy.

Rollback documentation uses the recorded SHA. The application must not run destructive reset commands automatically in the MVP.

## Failure behavior

| Failure | Required behavior |
|---|---|
| Invalid input path/pack | Stop before mutation and show a concise error. |
| LLM unavailable | Switch only when `DEMO_MODE` is explicitly enabled; otherwise fail. |
| Invalid structured response | Reject it; optionally retry once; then mark manual/fail. |
| Scope empty | Return a valid empty scope and stop before transform. |
| Path escapes repository | Reject the path and fail the run. |
| Syntax check fails | Set `syntax_ok=false`, mark manual, and fail verification. |
| Build/test fails or times out | Return `passed=false`; never commit or show merge-ready status. |
| Report generation fails | Preserve core run results and render a minimal deterministic summary. |

## Security notes

The demo must be described as operating on a trusted local fixture. Subprocess execution against arbitrary uploaded code is remote-code execution by design. A production version requires isolated containers, no host secrets in the runtime, network restrictions, resource limits, ephemeral workspaces, command allowlisting, archive traversal protection, and repository-size limits.

## Extension path after the hackathon

- Split ingest from profile and support URL/ZIP inputs safely.
- Run verification in ephemeral containers.
- Add language adapters and manifest parsers.
- Add bounded repair with per-file budgets.
- Persist runs and stream events through an API.
- Add authenticated GitHub App-based PR creation.
- Add human approval before mutation and before push.

These extend the same contracts; they do not change the principle that migration knowledge is supplied as data.
