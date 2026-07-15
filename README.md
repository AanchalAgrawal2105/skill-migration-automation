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
loads the production stage modules. Pending modules fail explicitly until their
owners implement them.

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

