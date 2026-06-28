# Runtime State Migration Design

## Objective

Move Hermes runtime state and logs out of the source repository into the current user's local application-data directory without losing existing data or changing normal CLI behavior.

## Scope

This change covers mutable root-runtime state currently stored under `memory/` and mutable employee-runtime state under `data/`. It also covers path resolution, one-time migration, atomic writes, log redaction, repository ignore rules, and automated tests.

It does not introduce a database, change task semantics, redesign authentication, migrate the separate G0DM0D3 application, delete repository files, or rotate external credentials.

## Runtime Data Location

The default data root on Windows is `%LOCALAPPDATA%\Hermes`. If `LOCALAPPDATA` is unavailable, Hermes uses the platform-appropriate per-user local data directory. Tests and controlled deployments may override the root with `HERMES_DATA_DIR`.

The data root preserves recognizable subdirectories:

```text
Hermes/
  memory/
  employee/
  security/
  sources/
  logs/
  migration.json
```

Application code obtains paths from one path-resolution module. Domain modules do not construct repository-relative runtime paths.

## Migration Behavior

Migration runs before the first read or write using the new data root.

1. Acquire an exclusive migration lock in the destination root.
2. If the versioned migration marker reports completion, continue normally.
3. Discover known legacy files under repository `memory/` and `data/`.
4. Copy each existing legacy file to its mapped destination only when that destination does not exist.
5. Write each copied file through a temporary sibling followed by atomic replacement.
6. Write `migration.json` atomically with the migration version, timestamp, source root, and per-file result.
7. Release the lock.

Legacy files remain untouched as a backup. Existing destination files always win, preventing an old repository checkout from overwriting newer user state. A partially failed migration may be rerun safely because each file operation is idempotent and the completion marker is written last.

An unrecoverable migration failure stops the operation with a clear error rather than silently creating split state.

## Persistence Safety

All JSON state writes use an atomic temporary-file-and-replace operation. Parent directories are created with user-only permissions where supported. State readers validate the expected JSON shape before use and report corrupt files without overwriting the only copy.

Append-only log writes remain append operations. Log entries pass through a shared redactor before persistence.

## Redaction

The redactor masks common API keys, bearer tokens, authorization headers, password/secret/token assignments, and provider error text that echoes credentials. Redaction occurs at the persistence boundary so callers cannot accidentally bypass it.

Redaction is defense in depth, not a credential-management system. Configuration continues to prefer environment variables over stored secrets.

## Repository Hygiene

`.gitignore` excludes generated runtime JSON, logs, migration markers, local environment files, caches, and temporary atomic-write files. Sanitized test fixtures remain tracked under `tests/fixtures/`.

Existing tracked legacy files are not deleted by runtime code. Their removal from version control is a separate, explicit repository cleanup step after migration has been verified.

## Compatibility

Public CLI commands and in-memory result shapes remain unchanged. Modules that currently accept explicit paths continue to honor those paths. Only default runtime locations change.

## Testing

Implementation follows test-driven development. Tests cover:

- default and `HERMES_DATA_DIR` path resolution;
- migration of existing files;
- preservation of legacy source files;
- destination-wins conflict handling;
- idempotent reruns;
- partial failure without a false completion marker;
- atomic JSON writes;
- redaction of representative secret formats;
- CLI behavior using an isolated temporary data root.

The full Python suite and repository validation command must pass before completion is claimed.

## Rollout and Recovery

The first release logs a concise migration summary without sensitive values. Recovery consists of stopping Hermes, correcting the destination problem, and rerunning; unchanged legacy files remain available. Rollback to the old version remains possible because migration copies rather than moves source files.

## Acceptance Criteria

- New runtime writes occur outside the repository by default.
- Existing recognized runtime state is copied automatically exactly once without deleting source files.
- Existing destination data is never overwritten by migration.
- Failed migration cannot be recorded as complete.
- Persisted logs mask supported secret patterns.
- Tests isolate all state through temporary directories.
- No public CLI command changes are required.
