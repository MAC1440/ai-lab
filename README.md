# AI Lab

AI Lab is a personal, local-first coding workbench for bounded Python,
Next.js, and Unity changes. It combines local Ollama models with reviewable
change sets, deterministic project context, verification, repair history,
knowledge retrieval, and persistent task state.

It is designed for one developer on one machine. It is not a hosted,
multi-user product.

## MVP capabilities

- Local agent chat with streamed tool, retrieval, and answer events
- Workspace-confined file inspection and search
- Persistent project tasks with planning, generation, review, and verification
- Transactional multi-file application with stale-context rejection
- Bounded repair tasks and restart recovery
- Deterministic project detection and persistent relevant-file indexing
- Python, Next.js, and Unity verification profiles
- Local document and Unity knowledge retrieval through ChromaDB
- Model/provider assignments, capability benchmarks, and reliability runs
- Runtime hardware guidance and persistent performance metrics
- Backup, restore, diagnostics, and identity-aware Windows startup

## Requirements

- Windows 10 or 11
- Python 3.11 or 3.12
- Node.js 20 or newer
- Git
- Ollama

The default local models are:

```text
granite4.1:3b
nomic-embed-text
```

Granite is fast on modest hardware but can fail complex structured coding
tasks. AI Lab preserves those failures as model limitations rather than
weakening file-safety rules.

## Setup

From PowerShell at the repository root:

```powershell
.\setup-ai-lab.ps1
.\start-ai-lab.ps1
```

For an optimized production frontend:

```powershell
.\setup-ai-lab.ps1 -Build -SkipModels
.\start-ai-lab.ps1 -Mode production
```

The launcher refuses to reuse another application, another checkout, an older
AI Lab process, or a production build that does not match the current source.
It never stops a conflicting process automatically.

## Normal workflow

1. Open **Settings** and select the actual target workspace.
2. Open **Tasks** and create one bounded goal.
3. Inspect the model-generated plan and indexed planning evidence.
4. Review every proposed file and complete change set.
5. Approve and verify.
6. Use the bounded repair flow when verification fails.
7. Run the real application manually before committing its changes.

AI Lab changes the selected working tree. Git commits and pushes remain under
your control.

## Health and diagnostics

```powershell
.\start-ai-lab.ps1 -Check
.\start-ai-lab.ps1 -Status
.\start-ai-lab.ps1 -Diagnostics
```

The diagnostics archive contains service identity, version, installation, and
log metadata. It excludes prompts, log contents, databases, source files,
credentials, and environment-variable values.

## Validation

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm test
npm run lint
npx tsc --noEmit --incremental false
npm run build

cd ..
.\backend\.venv\Scripts\python.exe -m unittest launcher.test_ai_lab_launcher -v
```

See [MVP release and acceptance](docs/mvp-release.md) for the final manual
checkpoint and known boundaries.
