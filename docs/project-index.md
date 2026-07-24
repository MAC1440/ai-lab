# Persistent project index

The project index improves the planning stage's relevant-file selection without
changing AI Lab's approval or stale-file safety model.

## What is stored

The SQLite database contains:

- workspace-relative source paths;
- file size, modification timestamp, and SHA-256 fingerprint;
- detected language;
- Python, TypeScript/JavaScript, and C# declarations;
- import/reference strings and resolved workspace dependency edges;
- refresh statistics and errors.

Full source contents are never stored. `ProjectContextService` reads selected
files from the current workspace under its existing size budgets, and
`TaskContextService` still freezes complete planned target files with current
SHA-256 hashes before generation.

## Incremental refresh

Before a Project Task planning call, AI Lab:

1. walks supported source files under the selected workspace;
2. skips standard generated folders, symlinks, `.gitignore` matches, oversized
   files, unsupported types, and invalid UTF-8;
3. compares file size and nanosecond modification time with the stored
   fingerprint;
4. reparses only new or changed files;
5. removes deleted files;
6. resolves dependency edges from the updated metadata.

The default limits are 20,000 files and 1.5 MB per source file. These can be
changed with:

```dotenv
PROJECT_INDEX_DB_PATH=data/project-index.sqlite3
PROJECT_INDEX_MAX_FILES=20000
PROJECT_INDEX_MAX_FILE_BYTES=1500000
```

If indexing fails, task planning falls back to the earlier deterministic
manifest, prompt-path, tree, and direct-import collector. An index problem
therefore reduces relevance quality but does not disable Project Tasks.

## Ranking

The query is split into normalized words, snake_case parts, and CamelCase
parts. Candidate scores use:

- exact workspace paths mentioned in the goal;
- filename and directory matches;
- declaration/symbol matches;
- one-hop imports and reverse dependencies;
- a small manifest preference.

Only candidates inside the detected project root are included in mixed
workspaces. The highest-ranked files are included after prompt-mentioned files
and project manifests, subject to the existing context budget.

Every stored `planning_model_run` artifact contains the selected candidates,
scores, and reasons. The Project Task UI displays this as **Indexed planning
evidence**.

## UI and API

Use **Manage → Index** to:

- view index age and counts;
- refresh changed files;
- rebuild every file;
- test a task description and inspect ranked results.

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/project-index/status` | Read selected-workspace index status |
| `POST` | `/project-index/refresh` | Incremental refresh or full rebuild |
| `POST` | `/project-index/query` | Rank relevant files for text |

Example query:

```json
{
  "query": "Add session expiry handling to AuthService",
  "limit": 8,
  "refresh": true
}
```

The index database is included in AI Lab's normal system diagnostics and
secret-free application backup. It contains no selected-project source text.

## When to rebuild

Normal Project Tasks automatically perform an incremental refresh. Use
**Rebuild** only after:

- changing ignore rules;
- moving a large folder tree outside AI Lab;
- suspecting stale relevance results;
- upgrading the index format in a future release.
