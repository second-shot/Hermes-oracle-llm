# Runtime State Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move mutable Hermes state and logs to a per-user application-data directory through an idempotent, non-destructive migration with atomic persistence and secret redaction.

**Architecture:** Add one `runtime_state.py` boundary that resolves paths, migrates legacy files, redacts logs, and performs atomic JSON writes. Adapt both Python runtimes to obtain paths through that boundary while retaining explicit path injection for tests and existing callers.

**Tech Stack:** Python 3 standard library (`pathlib`, `json`, `tempfile`, `os`, `re`, `shutil`, `msvcrt`/portable lock fallback), pytest.

---

## File map

- Create `runtime_state.py`: data-root resolution, legacy mapping, migration lock/marker, atomic JSON writes, redaction.
- Create `tests/test_runtime_state.py`: focused path, migration, failure, atomic-write, and redaction tests.
- Create `tests/test_memory_store.py`: behavior tests for root memory persistence using an isolated data root.
- Modify `memory/store.py`: delegate default paths, migration, atomic JSON persistence, and redaction.
- Modify `hermes_employee.py`: replace repository-relative mutable data constants and JSON writes with shared runtime-state services.
- Modify `.gitignore`: exclude repository runtime artifacts and temporary files while preserving fixtures.
- Modify `README.md`: document the new data root, override, migration, and recovery behavior.

### Task 1: Resolve the per-user runtime root

**Files:**
- Create: `runtime_state.py`
- Create: `tests/test_runtime_state.py`

- [ ] **Step 1: Write failing path-resolution tests**

```python
from pathlib import Path

from runtime_state import resolve_data_root


def test_environment_override_wins(monkeypatch, tmp_path):
    override = tmp_path / "custom"
    monkeypatch.setenv("HERMES_DATA_DIR", str(override))
    assert resolve_data_root() == override.resolve()


def test_windows_local_appdata_is_default(monkeypatch, tmp_path):
    monkeypatch.delenv("HERMES_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert resolve_data_root() == (tmp_path / "Hermes").resolve()
```

- [ ] **Step 2: Verify RED**

Run: `pytest tests/test_runtime_state.py -q`

Expected: collection fails because `runtime_state` does not exist.

- [ ] **Step 3: Implement minimal path resolution**

```python
def resolve_data_root(env=None, home=None):
    values = os.environ if env is None else env
    if values.get("HERMES_DATA_DIR"):
        return Path(values["HERMES_DATA_DIR"]).expanduser().resolve()
    if values.get("LOCALAPPDATA"):
        return (Path(values["LOCALAPPDATA"]) / "Hermes").resolve()
    base = Path.home() if home is None else Path(home)
    return (base / ".local" / "share" / "Hermes").resolve()
```

- [ ] **Step 4: Verify GREEN**

Run: `pytest tests/test_runtime_state.py -q`

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add runtime_state.py tests/test_runtime_state.py
git commit -m "feat: resolve Hermes runtime data root"
```

### Task 2: Add idempotent legacy migration

**Files:**
- Modify: `runtime_state.py`
- Modify: `tests/test_runtime_state.py`

- [ ] **Step 1: Write failing migration tests**

Add tests that create `memory/structured.json`, `memory/logs.md`, and representative `data/employee`, `data/security`, and `data/sources` files under a temporary legacy root. Assert that `migrate_legacy_state(legacy_root, data_root)`:

```python
assert (data_root / "memory" / "structured.json").read_text() == source_text
assert legacy_file.exists()
assert json.loads((data_root / "migration.json").read_text())["version"] == 1
```

Add separate tests asserting destination-wins and a second invocation makes no content changes.

- [ ] **Step 2: Verify RED**

Run: `pytest tests/test_runtime_state.py -q`

Expected: failures because `migrate_legacy_state` is undefined.

- [ ] **Step 3: Implement the migration contract**

Define an explicit allowlist:

```python
LEGACY_MAPPINGS = {
    Path("memory/structured.json"): Path("memory/structured.json"),
    Path("memory/logs.md"): Path("logs/sessions.md"),
    Path("data/employee"): Path("employee"),
    Path("data/security"): Path("security"),
    Path("data/sources"): Path("sources"),
}
```

Implement `migrate_legacy_state()` so it acquires an exclusive destination lock, copies only recognized files whose destination is absent, uses atomic sibling replacements, and writes the version-1 marker last. Store only relative paths and status values in the marker; do not store file contents.

- [ ] **Step 4: Add and verify the failure test**

Monkeypatch the internal copy operation to fail on the second file. Assert the exception propagates and `migration.json` does not exist.

Run: `pytest tests/test_runtime_state.py -q`

Expected: all migration tests pass.

- [ ] **Step 5: Commit**

```powershell
git add runtime_state.py tests/test_runtime_state.py
git commit -m "feat: migrate legacy Hermes state safely"
```

### Task 3: Add atomic JSON persistence and redaction

**Files:**
- Modify: `runtime_state.py`
- Modify: `tests/test_runtime_state.py`

- [ ] **Step 1: Write failing atomic-write and redaction tests**

```python
def test_atomic_json_write_replaces_document(tmp_path):
    path = tmp_path / "state.json"
    atomic_write_json(path, {"version": 1})
    atomic_write_json(path, {"version": 2})
    assert json.loads(path.read_text()) == {"version": 2}
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.parametrize("value", [
    "Authorization: Bearer abcdefghijklmnop",
    "api_key=abcdefghijklmnop",
    "password: supersecret123",
    "sk-abcdefghijklmnopqrstuvwxyz",
])
def test_redact_masks_secret_values(value):
    redacted = redact_text(value)
    assert "abcdefghijklmnop" not in redacted
    assert "supersecret123" not in redacted
```

- [ ] **Step 2: Verify RED**

Run: `pytest tests/test_runtime_state.py -q`

Expected: failures because the new functions do not exist.

- [ ] **Step 3: Implement minimal persistence utilities**

Use `tempfile.NamedTemporaryFile(delete=False, dir=path.parent)`, flush and `os.fsync()`, then `os.replace()`. Clean up the temporary path in `finally`. Implement compiled, allowlisted credential patterns and replace secret values with `[REDACTED]`.

- [ ] **Step 4: Verify GREEN**

Run: `pytest tests/test_runtime_state.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add runtime_state.py tests/test_runtime_state.py
git commit -m "feat: add atomic state writes and log redaction"
```

### Task 4: Migrate the root memory store

**Files:**
- Modify: `memory/store.py`
- Create: `tests/test_memory_store.py`

- [ ] **Step 1: Write failing store tests**

Set `HERMES_DATA_DIR` to `tmp_path / "runtime"`, reload `memory.store`, call `update_memory()` and `log_session()`, then assert:

```python
assert (runtime / "memory" / "structured.json").exists()
assert (runtime / "logs" / "sessions.md").exists()
assert not (repo_root / "memory" / "new-runtime-file.json").exists()
assert "secret-value-123" not in sessions.read_text()
```

- [ ] **Step 2: Verify RED**

Run: `pytest tests/test_memory_store.py -q`

Expected: paths still target repository `memory/` or redaction assertion fails.

- [ ] **Step 3: Implement the adapter**

Replace string constants with functions that call `ensure_runtime_state(repository_root)` and return paths beneath its data root. Keep `read_memory(prompt)`, `update_memory(prompt, response)`, and `log_session(user_input, output)` signatures stable. Replace broad `except:` with explicit missing/corrupt-file handling and use `atomic_write_json()`.

- [ ] **Step 4: Verify GREEN and regression coverage**

Run: `pytest tests/test_memory_store.py tests/test_hermes_local_first.py -q`

Expected: all selected tests pass.

- [ ] **Step 5: Commit without unrelated user changes**

```powershell
git add memory/store.py tests/test_memory_store.py
git commit -m "refactor: store Hermes memory outside repository"
```

### Task 5: Migrate employee CLI persistence

**Files:**
- Modify: `hermes_employee.py`
- Create: `tests/test_employee_runtime_paths.py`

- [ ] **Step 1: Write failing CLI isolation test**

Launch the CLI in a subprocess with `HERMES_DATA_DIR` set to a temporary directory and run `status`. Assert the command succeeds, files appear beneath `employee/`, `security/`, and `sources/`, and repository `data/` mtimes remain unchanged.

- [ ] **Step 2: Verify RED**

Run: `pytest tests/test_employee_runtime_paths.py -q`

Expected: repository-relative `data/` files are touched or destination files are absent.

- [ ] **Step 3: Adapt constants and writes**

Resolve `DATA_EMPLOYEE`, `DATA_SECURITY`, and `DATA_SOURCES` from `ensure_runtime_state(ROOT)`. Delegate `write_json()` to `atomic_write_json()`. Pass appended log content through `redact_text()` before writing. Keep the skill registry as repository configuration rather than mutable runtime data.

- [ ] **Step 4: Verify GREEN**

Run: `pytest tests/test_employee_runtime_paths.py -q`

Expected: all tests pass and source-tree mtimes remain unchanged.

- [ ] **Step 5: Commit**

```powershell
git add hermes_employee.py tests/test_employee_runtime_paths.py
git commit -m "refactor: isolate employee runtime state"
```

### Task 6: Repository hygiene and operator documentation

**Files:**
- Modify: `.gitignore`
- Modify: `README.md`
- Create: `tests/fixtures/runtime-state/.gitkeep`

- [ ] **Step 1: Add ignore-policy test**

Create a test that runs `git check-ignore` for representative runtime files and asserts `tests/fixtures/runtime-state/.gitkeep` is not ignored.

- [ ] **Step 2: Verify RED**

Run: `pytest tests/test_repository_hygiene.py -q`

Expected: runtime paths or atomic temporary files are not ignored.

- [ ] **Step 3: Update ignore rules and documentation**

Add rules for `.hermes/`, repository `memory/*.json`, `memory/logs.md`, mutable `data/**` runtime outputs, `*.tmp`, `.env*` except `.env.example`, and local caches. Use negated rules for `tests/fixtures/**`.

Document `%LOCALAPPDATA%\Hermes`, `HERMES_DATA_DIR`, copy-not-move migration, destination-wins behavior, recovery, and the fact that old tracked state must be removed through a separate reviewed cleanup.

- [ ] **Step 4: Verify GREEN**

Run: `pytest tests/test_repository_hygiene.py -q`

Expected: all ignore-policy assertions pass.

- [ ] **Step 5: Commit**

```powershell
git add .gitignore README.md tests/fixtures/runtime-state/.gitkeep tests/test_repository_hygiene.py
git commit -m "docs: document isolated Hermes runtime state"
```

### Task 7: Full verification

**Files:**
- Verify only; fix failures in the smallest owning task before continuing.

- [ ] **Step 1: Run the complete Python suite**

Run: `pytest -q`

Expected: zero failures and zero errors.

- [ ] **Step 2: Run built-in validation against an isolated root**

```powershell
$env:HERMES_DATA_DIR = Join-Path $env:TEMP 'hermes-validation'
python hermes_employee.py validate
```

Expected: `VALIDATE: OK`.

- [ ] **Step 3: Verify repository cleanliness boundaries**

Run: `git status --short`

Expected: no new runtime files; pre-existing user changes remain untouched.

- [ ] **Step 4: Review the final diff**

Run: `git diff HEAD~6 -- runtime_state.py memory/store.py hermes_employee.py tests .gitignore README.md`

Expected: only planned migration, persistence, tests, ignore rules, and documentation changes.

- [ ] **Step 5: Record verification evidence**

Report exact commands, exit codes, pass counts, any skipped tests, and pre-existing uncommitted files. Do not claim completion if any required command fails.
