# Refer AI Platform Migration Agent — Product Brief

## Product statement

Refer is a generic, specification-driven migration agent. Given a source repository, a plain-English migration goal, and an optional YAML knowledge pack, it profiles the repository, plans the migration, edits only the relevant files, and verifies the result with deterministic tooling.

The one-hour hackathon build demonstrates the smallest credible loop:

> Profile → Plan → Transform → Verify

The migration itself is data. No migration-specific rules may be embedded in pipeline code. Known migration details belong in the user goal or an optional knowledge pack.

## Target user

A developer or platform engineer who needs to upgrade an SDK, framework, API, language feature, dependency, or configuration across an unfamiliar repository and wants a reviewable starting point rather than an unverified code dump.

## User problem

Repository migrations are repetitive but risky. A developer must discover the stack, locate affected call sites, understand breaking changes, make consistent edits, run the right checks, document risk, and preserve a rollback point. Existing one-off scripts are reliable but narrow; unconstrained LLM agents are flexible but difficult to trust.

Refer combines semantic LLM planning and editing with deterministic repository inspection, diffs, syntax checks, and tests.

## One-hour outcome

At the end of 60 minutes, the team must be able to demonstrate:

1. A user supplies a local demo repository, a migration goal, and optionally a knowledge-pack path.
2. The system detects the repository language, dependency manifests, file tree, and available test command.
3. An LLM or deterministic demo fallback returns a typed migration plan.
4. Relevant files are identified and transformed one file at a time.
5. The system displays a unified diff and runs syntax/tests.
6. The final result clearly reports pass/fail and the rollback commit SHA.
7. A second goal or knowledge pack can be used without changing pipeline code.

## MVP scope

### Must ship

- Frozen Pydantic stage contracts.
- Local-path repository ingestion; initialize Git when necessary and capture `HEAD` as the rollback anchor.
- Python repository profiling, with a registry structure that can support other languages.
- Goal and optional YAML pack passed into planning and transformation prompts.
- Per-file transformation and unified diff generation.
- Subprocess verification with a timeout.
- A prepared demo repository and at least one deterministic test.
- A single runnable interface: CLI or minimal Streamlit UI.
- A visible failure state; failed verification must never be presented as success.

### Should ship if core flow works by minute 45

- Markdown migration, risk, and rollback reports.
- Live stage status in Streamlit.
- One bounded repair attempt.
- A second migration demonstration using a different goal or pack.

### Explicitly deferred

- Arbitrary remote repository cloning and uploaded ZIP handling.
- Docker isolation and dependency installation.
- Production security hardening for untrusted repositories.
- GitHub push and live PR creation; show a PR preview instead.
- Multi-language verification beyond the registry skeleton.
- General false-positive filtering through a second LLM pass.
- Production-grade streaming, persistence, authentication, and concurrent jobs.

## Core user story

As a developer, I provide a repository and describe a migration. I can inspect the proposed plan and diff, see which deterministic checks ran, and know whether the result passed, needs review, or must be completed manually.

## Acceptance criteria

- The same application code accepts two different migration goals.
- No occurrence of the demo migration's old or new API is hardcoded under `app/`; migration-specific strings are confined to packs and demo fixtures.
- Every stage consumes or updates `MigrationRun` using the frozen contracts.
- Original repository state is recoverable from `rollback_anchor`.
- Each modified file has a rationale, diff, `syntax_ok`, and change kind.
- Verification records commands, bounded logs, and pass/fail status.
- A transformation or verification failure is surfaced and does not trigger commit/PR success.
- The primary demo completes in under three minutes after setup.

## Success measures

| Measure | One-hour target |
|---|---:|
| End-to-end controlled demo | 1 successful run |
| Different goals without pipeline edits | 2 |
| Core stages visible | 4/4 |
| Verification falsely reported as passing | 0 |
| Manual steps during primary demo | 0 |
| Primary demo runtime | < 3 minutes |

## Product principles

1. Migration knowledge is input data, not branching application logic.
2. The LLM proposes and edits; deterministic tools decide whether code passes.
3. A narrow, honest verified demo is better than a broad simulated product.
4. Every stage produces inspectable, typed artifacts.
5. Failure and uncertainty are first-class outputs.

## Risks and mitigations

| Risk | Mitigation in the one-hour build |
|---|---|
| LLM latency or unavailable credentials | Provide checked-in mock structured responses behind an explicit `DEMO_MODE`; label them in the UI. |
| Generated code fails | Run syntax and tests; keep the diff and mark the run failed/manual. |
| Scope expands to the full nine-stage design | Freeze must-have scope at minute 5; add features only after an end-to-end run. |
| Four branches do not integrate | Freeze schemas and function signatures by minute 8; integrate continuously into one shared branch. |
| Demo repository surprises the team | Use a tiny controlled fixture with local-only dependencies and pre-run both goals. |
| Reviewers doubt genericity | Run a second migration by changing only the goal/pack. |

## Decisions required in the first three minutes

The team lead asks these questions once. If there is no immediate answer, use the defaults and continue.

1. **Is an OpenAI API key available and approved for the demo?** Default: support both live LLM and explicit `DEMO_MODE=1`, rehearse with live mode once, and keep mock mode as fallback.
2. **Which teammate is strongest in UI/demo delivery?** Default: assign that person to Role D in `01-team-roles.md`.
3. **Must the final demo open a real GitHub PR?** Default: no; render a PR preview because credentials and network are outside the one-hour critical path.
4. **Is Streamlit already installed?** Default: use a CLI first, then add Streamlit only after minute 40.

## Demo narrative

“Give Refer a repository and a goal. It profiles the codebase, turns the goal into a typed plan, changes only scoped files, and proves the result with actual tests. Migration knowledge is supplied as data, so we can switch migrations without changing the engine.”
