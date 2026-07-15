# Refer Migration Agent

Refer is a specification-driven backbone for technology migrations. The
orchestrator is deliberately unaware of individual SDKs, languages, frameworks,
and migration recipes. Those details enter through a goal, an optional knowledge
pack, and pluggable stage implementations.

This repository currently contains the Role A foundation:

- frozen Pydantic stage contracts;
- a generic, runtime-loadable stage protocol;
- sequential orchestration with immutable progress snapshots;
- truthful failure handling that preserves partial results;
- CLI and fixture-backed integration mode;
- scaffolds for the nine production stages;
- contract and orchestration tests.

Role B's deterministic repository profiling and verification and Role C's typed
LLM migration engine are integrated with that foundation. Live mode uses the
OpenAI Responses API; explicit demo mode uses checked-in structured fixtures;
and packs with literal `transform.replacements` can run offline.

## Run the backbone

The fixture mode proves stage integration without claiming that model-driven or
repository stages have been implemented:

```bash
python -m app.main \
  --repo demo/sample-repo \
  --goal "Migrate an SDK to its supported API" \
  --fixture-dir tests/fixtures
```

Print machine-readable output with `--json`. Without `--fixture-dir`, the CLI
loads the production stages.

Run Role C's structured fixture mode with a pack that declares
`demo.fixture_id`:

```bash
python -m app.main \
  --repo ./some-repo \
  --goal "Migrate client construction" \
  --pack packs/client-call-upgrade.yaml \
  --demo-mode
```

For live mode, install the OpenAI SDK, set `OPENAI_API_KEY`, and set
`REFER_MODEL` to an available structured-output model. Secrets must not be
stored in packs, fixtures, or command output.

## Create a migration PR

The production pipeline now runs the PR stage after report generation. When
verification passes, it creates a migration branch and commits the changed
files. By default this stays local so demos cannot accidentally push to an
upstream repository.

To push the branch and open a real GitHub pull request, authenticate the GitHub
CLI for the target repository and pass `--create-pr`:

```bash
python -m app.main \
  --repo ./target-repo \
  --goal "Rename the deprecated helper" \
  --pack packs/rename-greeting.yaml \
  --create-pr \
  --pr-base main
```

The PR stage refuses to run when verification failed, when a changed file needs
manual review, or when Git/GitHub commands fail.

## Implement a stage

Each stage exports a function with this contract:

```python
def run(run: MigrationRun, context: StageContext) -> MigrationRun:
    ...
```

The context contains the repository path, goal, optional pack path, demo-mode
flag, and an injectable service map. A stage updates only its portion of the run.
Migration-specific knowledge must never be added to `pipeline.py`.

Run custom stages without editing the orchestrator:

```bash
python -m app.main \
  --repo ./some-repo \
  --goal "Upgrade the framework" \
  --stage my_plugin.profile:run \
  --stage my_plugin.plan:run \
  --stage my_plugin.transform:run \
  --stage my_plugin.verify:run
```

## Verify

```bash
pytest
python -m app.main --repo demo/sample-repo --goal demo \
  --fixture-dir tests/fixtures
```

The design and one-hour delivery documents are in `00-product-brief.md` through
`04-implementation-plan.md`.
