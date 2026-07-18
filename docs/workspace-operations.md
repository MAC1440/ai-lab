# Reviewable workspace operations

AI Lab agents can propose creating/updating text files, deleting one text file,
moving or renaming one text file, and creating a directory. Every operation is
confined to the selected workspace and requires human approval.

`propose_file_change` handles create/update. `propose_path_operation` handles
`delete`, `move`, and `mkdir`. Existing files must be read before mutation.
Moves cannot overwrite a destination, stale source files are rejected, and
recursive directory deletion is intentionally unsupported.

Existing SQLite databases are migrated automatically with the nullable
`destination_path` column.
