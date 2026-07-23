# Reliability benchmarks

AI Lab has two distinct benchmark layers:

1. Model benchmarks measure whether one configured model can return valid
   planning, generation, and repair structures.
2. Reliability benchmarks measure whether the complete project-task workflow
   works across model calls, deterministic context, validation, proposals,
   transactional application, and recovery guards.

Reliability benchmarks never use the selected project. Each scenario receives
its own disposable workspace and private SQLite databases under
`data/reliability-workspaces`. The workspace is deleted when the scenario
finishes or its stream is cancelled.

## Suites

### Quick

The quick suite contains three scenarios and normally makes two model calls:

- Python discount behavior: planning, generation, transactional application,
  syntax validation, and bounded behavior checks.
- Stale context rejection: changes a source file after context freezing and
  requires the task to stop.
- Transactional rollback: fails after the first write and compares the
  restored files byte-for-byte, including mixed CRLF/LF files.

### Full

The full suite contains seven scenarios and normally makes six model calls:

- Python discount behavior.
- Next.js typed status card.
- Unity typed damage input.
- Stale context rejection.
- Transactional rollback.
- Restart recovery for a process stopped during application.
- Durable recovery for a benchmark run interrupted by a backend restart.

One repetition therefore evaluates each configured planning/generation model
once per live project type. Two or three repetitions expose intermittent model
behavior rather than treating one success as reliable.

## Scoring

Every scenario records named assertions. Its score is:

```text
passed assertions / total assertions
```

A scenario passes only at `100%`. A run passes only when every scenario passes.
This deliberately avoids hiding a failed rollback or stale-file guard behind a
high average from easier model tasks.

Python code is parsed, compiled, and checked with a restricted AST evaluator.
Generated benchmark code is never executed in the FastAPI process. The
Next.js and Unity fixtures receive deterministic source-contract checks because
an isolated fixture does not contain a complete `node_modules` directory or
Unity installation. The normal project-task verification stage remains the
authoritative compiler/build check for real approved changes.

Each result also records:

- Effective agent assignment.
- Planning/generation model names.
- Aggregated token/request usage when the provider reports it.
- Duration.
- Proposal count and change-set ID.
- Fault type for safety scenarios.
- Error and assertion evidence.

## API

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/reliability-benchmarks/scenarios` | List the immutable catalog |
| `GET` | `/reliability-benchmarks/runs` | List durable summaries |
| `GET` | `/reliability-benchmarks/runs/{run_id}` | Read full evidence |
| `POST` | `/reliability-benchmarks/run/stream` | Stream an isolated run |

The stream is NDJSON. Swagger may display it as raw text because it is multiple
JSON documents separated by newlines.

Example request:

```json
{
  "suite": "full",
  "repetitions": 2,
  "agent_override": "assigned"
}
```

`assigned` uses the Coding agent for Python, Web for Next.js, and Unity for
Unity. A forced override is useful for comparing one model/agent configuration
against all project types.

## Headless use

Start the backend, then run:

```powershell
cd backend
python scripts/run_reliability_benchmarks.py --suite quick
python scripts/run_reliability_benchmarks.py --suite full --repetitions 3
```

The command exits `0` only when the complete suite passes, `1` for measured
scenario failures, and `2` when the API/stream cannot run. This makes it usable
in release scripts without parsing the console output.

## Persistence and cleanup

Defaults:

```text
data/reliability-benchmarks.sqlite3
data/reliability-workspaces/
```

Overrides:

```dotenv
RELIABILITY_BENCHMARK_DB_PATH=data/reliability-benchmarks.sqlite3
RELIABILITY_BENCHMARK_WORK_ROOT=data/reliability-workspaces
```

Running records become `interrupted` on the next startup. Disposable
workspaces are deleted in the runner's `finally` block. A stale directory left
by an operating-system hard termination contains benchmark fixtures only and
can be deleted safely while no benchmark is active.
