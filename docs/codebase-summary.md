# Codebase Summary

Technical overview of the `trobz_local` codebase structure, implementation patterns, and module responsibilities.

## Project Statistics

| Metric | Value |
|---|---|
| **Language** | Python 3.12+ |
| **Total LOC** | ~1,287 lines (core logic) + tests |
| **Core Modules** | 7 files (main, installers, utils, postgres, concurrency, exceptions, \__init\_\_) |
| **Test Modules** | tests/ directory with pytest unit tests |
| **Primary Frameworks** | Typer (CLI), Pydantic (validation), Rich (UI), GitPython (git) |
| **Concurrency Model** | ThreadPoolExecutor, max 4 workers, I/O-bound tasks |
| **License** | AGPL-3.0 |

## Module Breakdown

### `main.py` (473+ LOC)
**Purpose**: CLI entry point and command orchestration

**Responsibilities**:
- Define Typer application with 5 main commands
- Manage "newcomer mode" state (interactive confirmations)
- Orchestrate calls to installers, git operations, venv creation, and PostgreSQL user management
- Handle user interaction and progress reporting

**Key Commands**:
- `init`: Create directory structure
- `pull-repos`: Clone/update repositories
- `create-venvs`: Create Python virtual environments
- `install-tools`: Install from four sources
- `ensure-db-user`: Verify/create PostgreSQL user

**Key Functions**:
- `main()` - Typer callback and default behavior
- `_get_tasks()` - Build task list from config (with optional filtering)
- `_pull_repo()` - Git clone/update worker
- `_create_venvs()` - venv creation worker via odoo-venv
- `_run_installers()` - Orchestrate four-stage installer pipeline
- `_build_install_message()` - Format preview message for tools
- `ensure_db_user()` - PostgreSQL user management orchestrator

---

### `installers.py` (282 LOC)
**Purpose**: Multi-source tool installation strategies

**Strategies**:
1. **Scripts**: Download via wget/curl, execute with /bin/sh
2. **System Packages**: OS-aware (apt-get, pacman, brew) with platform defaults
3. **NPM Packages**: Global via pnpm install -g
4. **UV Tools**: Global via uv tool install

**Key Functions**:
- `install_scripts()` - Download and execute shell scripts with progress
- `install_system_packages()` - OS detection and package manager invocation
- `install_npm_packages()` - Parallel npm package installation
- `install_uv_tools()` - Parallel UV tool installation

**Pattern**: Each installer function:
- Takes list of items and optional dry_run flag
- Returns TaskResult(s) or boolean
- Uses run_tasks() for parallelization (except system packages)
- Progress callback signature: (progress, task_id, **kwargs)

---

### `utils.py` (264 LOC)
**Purpose**: Configuration validation, platform detection, utilities

**Pydantic Models**:
- `ConfigModel` - Root config with versions, tools, repos
- `ToolsConfig` - Tool specifications (uv, npm, script, system_packages)
- `ScriptItem` - Script definition with url and optional name
- `RepoConfig` - Repository definitions (odoo, oca)

**Validation**:
- Versions: Pattern `^\d+\.\d+$`
- UV tools: Pattern `^[a-zA-Z0-9][a-zA-Z0-9._\-\[\]@=<>!,]*$`
- NPM packages: Scoped and unscoped validation
- Scripts: HTTPS-only enforcement
- Repo names: Pattern `^[a-zA-Z0-9._-]+$`

**Key Functions**:
- `get_config()` - Load and validate config.toml with error handling
- `get_uv_path()` - Locate uv executable
- `get_os_info()` - Return {system, distro} for platform detection
- `confirm_step()` - Interactive confirmation in newcomer mode
- `GitProgress` class - Custom progress callback for GitPython

**Platform Defaults**: Arch, Ubuntu, macOS with curated default packages

---

### `concurrency.py` (60 LOC)
**Purpose**: Generic parallel task execution with progress tracking

**TaskResult Dataclass**:
```python
@dataclass
class TaskResult:
    name: str                      # Task identifier
    success: bool                  # Outcome
    message: str | None = None     # Status message
    error: Exception | None = None # Exception if failed
```

**Key Function**:
- `run_tasks(tasks, max_workers=4)` - Execute tasks in parallel
  - Task format: {name, func, args (optional)}
  - Progress reporting with Rich 3-column layout
  - Per-task error isolation
  - Graceful KeyboardInterrupt handling

---

### `exceptions.py` (38 LOC)
**Purpose**: Custom exception hierarchy for granular error handling

**Exception Classes**:
- `InstallerError` - Base exception
- `DownloadError(url, reason)` - Script download failures
- `ScriptExecutionError(script_name, reason)` - Script execution failures
- `PackageInstallError(package, reason)` - Installation failures
- `ExecutableNotFoundError(executable)` - Missing system executables

---

### `postgres.py` (191 LOC)
**Purpose**: PostgreSQL user management for Odoo development

**Responsibilities**:
- OS-aware PostgreSQL operations (Linux sudo vs macOS direct)
- Validate PostgreSQL identifiers and credentials
- Check PostgreSQL availability and user existence
- Create PostgreSQL users with CREATEDB permission
- Test database connections with created credentials

**Key Functions**:
- `_get_psql_base_cmd(system)` - Get OS-specific psql command prefix
- `validate_username(username)` - Validate PostgreSQL identifier format
- `validate_password(password)` - Validate password non-empty
- `check_postgres_running()` - Test PostgreSQL availability via pg_isready
- `check_user_exists(username, system)` - Check if user exists in PostgreSQL
- `create_user(username, password, system)` - Create user with CREATEDB, returns (success, error_msg)
- `verify_connection(host, user, password)` - Test connection with credentials

**Security Pattern**:
- Input validation: Regex-validated usernames (max 63 chars, alphanumeric + underscore)
- SQL injection prevention: psql variable binding (`:\"varname\"` for identifiers, `:'varname'` for strings)
- Environment isolation: Only PGPASSWORD env var passed during connection test
- No shell=True: All subprocess calls use argument lists (noqa: S603)

---

## Architecture Patterns

| Pattern | Implementation | Purpose |
|---|---|---|
| **Declarative Config** | TOML + Pydantic | Single source of truth for desired state |
| **Strategy Pattern** | Four installer strategies | Pluggable installation methods |
| **Command Pattern** | Typer commands | Discrete, composable CLI commands |
| **Builder Pattern** | Task construction in main.py | Dynamic task list generation |
| **Observer Pattern** | GitProgress + run_tasks | Real-time progress feedback |
| **Fail-Fast** | Config validation at startup | Early detection of configuration errors |

---

## Data Flow

```
User Command
    ↓
CLI (main.py) - Parse and route
    ↓
Config Loading (utils.py) - Validate {CODE_ROOT}/config.toml (uses get_code_root())
    ↓
Task Generation - Build list of operations
    ↓
Execution (concurrency.py) - ThreadPoolExecutor (max 4 workers)
    ↓
Progress Reporting (Rich) - Real-time UI updates
    ↓
Results Aggregation - TaskResult collection
    ↓
Summary Display - Success/failure reporting with exit code
```

The `get_code_root()` function (utils.py) resolves the code root directory by:
1. First checking for `TLC_CODE_DIR` environment variable
2. Falling back to `~/code` if not set

---

## External Dependencies

| Dependency | Version | Purpose |
|---|---|---|
| `typer` | Latest | CLI framework with type hints |
| `pydantic` | v2+ | Configuration validation with strict typing |
| `rich` | Latest | Terminal UI (progress bars, colors, trees) |
| `gitpython` | Latest | Programmatic git operations |
| `tomllib` | Built-in (Python 3.11+) | TOML parsing for Python 3.11+ |
| `tomli` | Latest (optional) | TOML parsing fallback for Python < 3.11 |

---

## Key Implementation Details

### Concurrency Model
- ThreadPoolExecutor with configurable max_workers (default: 4)
- I/O-bound: downloads, git operations, package installation
- Per-task error isolation: one failure doesn't block others

### Security Hardening
- **No shell=True**: All subprocess calls use argument lists
- **HTTPS enforcement**: Pydantic validator rejects non-HTTPS URLs
- **Path resolution**: shutil.which() for full executable paths
- **Input validation**: All config fields regex-validated

### Error Handling
- Configuration errors: Exit immediately with examples
- Task failures: Isolated and aggregated, exit 1 if any fail
- Cleanup: Temporary directories auto-deleted on function exit
- User interruption: Graceful shutdown with KeyboardInterrupt handler
