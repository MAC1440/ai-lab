# AI Lab Launcher

The launcher owns local application startup without changing the agent runtime.
It starts FastAPI and Next.js in the correct folders, waits for health checks,
opens the browser, records logs, and stops only processes it started.

It deliberately does not start or stop Ollama. Ollama may be shared by other
applications, so the launcher reports its health without taking ownership of it.

## Commands

From the repository root on Windows:

```powershell
.\setup-ai-lab.ps1
.\start-ai-lab.ps1
```

Build and use the optimized Next.js server:

```powershell
.\setup-ai-lab.ps1 -Build -SkipModels
.\start-ai-lab.ps1 -Mode production
```

Validate installation without starting anything:

```powershell
.\start-ai-lab.ps1 -Check
```

Create a desktop shortcut:

```powershell
.\install-ai-lab-shortcut.ps1
```

Logs are stored under `backend/data/logs`. This location is already ignored by
Git. If either server was running before the launcher, it is reused and is not
stopped when the launcher exits.

## Tests

```powershell
python -m unittest launcher.test_ai_lab_launcher -v
```
