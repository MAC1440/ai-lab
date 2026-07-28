# AI Lab MVP release and acceptance

## Release definition

The MVP is complete when AI Lab can take one bounded project task through:

```text
workspace selection
→ deterministic context and index evidence
→ plan
→ generated reviewable change set
→ explicit approval
→ transactional application
→ verification
→ completion or bounded repair
```

The model does not need to pass every task. A small local model may fail to
produce a usable plan or change set. The application must surface that failure
without corrupting the selected workspace or losing task state.

## Automated release gate

Run from the repository root:

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
.\start-ai-lab.ps1 -Mode production -Check
```

All commands must pass before creating a source release.

## Manual acceptance gate

Use disposable repositories or branches for these checks.

### 1. Python task

- Select a small Python project.
- Ask for one behavior change affecting one or two files.
- Confirm indexed evidence points to relevant files.
- Review and approve the complete change set.
- Confirm Python verification passes or creates a bounded repair task.
- Restart AI Lab and confirm the task and verification history remain.

### 2. Next.js task

- Select a small Next.js App Router project.
- Ask for one UI change without new dependencies.
- Confirm the plan uses existing conventions and paths.
- Approve, verify lint/TypeScript/build, then test the page manually.

### 3. Unity task

- Select a disposable Unity project.
- Ask for a small typed C# behavior change.
- Confirm changes remain under `Assets`.
- Review the complete files and run available Unity/C# checks.
- Open the Unity scene and test the behavior manually.

### 4. Safety and lifecycle

- Start AI Lab in production mode.
- Change a runtime source file and confirm production `-Check` reports a stale
  build until setup rebuilds it.
- Start another service on port 3000 or 8000 and confirm AI Lab refuses to
  claim or stop it.
- Run `-Status` and verify both AI Lab services report an identity match.
- Run `-Diagnostics` and inspect that the ZIP contains no prompts, databases,
  credentials, environment values, source files, or log contents.

## Known MVP boundaries

- Granite 4.1 3B is fast but not consistently capable of complex structured
  generation and repair.
- AI Lab does not commit, push, or merge the target project's Git changes.
- Dependencies proposed by scaffolds or tasks are not installed automatically.
- The general chat agent is less reliable for large coding changes than
  Project Tasks.
- MCP remains an allow-listed, read-only integration boundary.
- Verification passing does not replace manual UI or Unity scene testing.
- This is a single-user local tool, not a secured network service.

## Post-MVP rule

After the automated and manual gates pass, freeze core MVP work. Add external
tools only when they remove a demonstrated bottleneck in real freelance or
Unity work; do not add integrations solely because they are available.
