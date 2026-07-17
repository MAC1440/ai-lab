# Safe Repair Tasks

Safe Repair Tasks connect AI Lab's existing verification and change-approval
features into one durable workflow.

## Lifecycle

1. A predefined workspace verification check fails.
2. The frontend creates a repair task from the stored verification run.
3. The coding agent receives fresh context and enforced `propose` tool policy.
4. Every proposal from that agent turn receives one `change_set_id` and the
   repair task's `repair_task_id`.
5. The user reviews proposals individually or resolves the related set.
6. Approved content is written only after the existing stale-file and
   workspace checks pass.
7. The original verification profile runs again and records its result against
   the task.
8. Only a passing verification resolves the task as `passed`.

Repair tasks and proposals survive backend restarts in SQLite. The default
files are `backend/data/repairs.sqlite3` and
`backend/data/changes.sqlite3`; the existing `.gitignore` excludes the data
directory.

## Safety boundaries

- The model cannot provide verification shell commands.
- A repair request uses the coding agent and enforced `propose` policy.
- Proposals still require human review.
- Proposal approval checks the active workspace and original file hash.
- A passed task means the configured check passed, not that every possible
  project behavior was proven correct.
- Dismissing a task never applies its proposals.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/repairs` | Create or return a task for a failed run |
| `GET` | `/repairs` | List tasks for the active workspace |
| `GET` | `/repairs/{task_id}` | Get a task with linked proposals |
| `POST` | `/repairs/{task_id}/dismiss` | Hide an unresolved task |
| `POST` | `/repairs/{task_id}/reopen` | Reopen a resolved task |
| `POST` | `/changes/sets/{id}/approve` | Approve a related proposal set |
| `POST` | `/changes/sets/{id}/reject` | Reject a related proposal set |

The Pydantic stream request accepts an optional `repair_task_id`. The backend
generates the `change_set_id`; the model does not control either identifier.

The verification stream request accepts an optional `repair_task_id`. When its
terminal `verification_done` event arrives, the backend updates the matching
task before sending the event to the frontend.

## Manual verification

From `backend`:

```bash
python -m pytest -q
ruff check .
```

From `frontend`:

```bash
npm run lint
npm run build
```

Then test the complete UI flow using a deliberately failing project test:

1. Select the project workspace.
2. Run its verification profile.
3. Choose **Ask agent to fix**.
4. Send the prepared coding-agent request.
5. Review the produced diff.
6. Approve it and rerun the check from **Repairs**.
7. Confirm that the task changes to **passed**.
