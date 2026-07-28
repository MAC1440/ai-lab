# AI Lab Launcher

The launcher starts FastAPI and Next.js from the correct checkout, records
bounded logs, opens the browser, and stops only processes it started. Ollama
remains independently managed because other local applications may share it.

## Identity and stale-build protection

Every launcher run calculates:

- a checkout ID from the resolved repository path;
- a SHA-256 fingerprint of runtime source and configuration.

The backend and frontend expose those values through their health endpoints.
A running service is reused only when its service name, checkout ID, and source
fingerprint all match. A conflicting service is reported and left untouched.

Production builds also contain a source marker written by
`setup-ai-lab.ps1 -Build`. Production startup fails when that marker is missing
or stale.

## Commands

```powershell
# Development
.\setup-ai-lab.ps1
.\start-ai-lab.ps1

# Production
.\setup-ai-lab.ps1 -Build -SkipModels
.\start-ai-lab.ps1 -Mode production

# Validate dependencies and production source marker
.\start-ai-lab.ps1 -Mode production -Check

# Inspect service/build/launcher state
.\start-ai-lab.ps1 -Status

# Create a privacy-safe local diagnostics archive
.\start-ai-lab.ps1 -Diagnostics
```

Logs are stored under `backend/data/logs` and entries older than 14 days are
removed when the launcher starts. `backend/data/launcher-state.json` records
`starting`, `running`, `stopped`, or `error` explicitly.

Diagnostics are written under `backend/data/diagnostics`. They contain log
metadata only, never log contents.

## Source release

After committing a clean, validated tree:

```powershell
.\package-ai-lab-release.ps1
```

This creates a Git-based ZIP and a SHA-256 checksum under `dist`. Runtime
databases, generated frontend state, editor configuration, and Git metadata are
excluded.

## Tests

```powershell
python -m unittest launcher.test_ai_lab_launcher -v
```
