# System Architecture

High-level design and component interactions in `trobz_local`.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    User (CLI Interface)                      │
│                    tlc <command> [options]                   │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
   ┌────▼──────┐         ┌───────▼────┐
   │  Newcomer  │         │  Dry-Run   │
   │   Mode     │         │   Preview  │
   └────┬──────┘         └────┬───────┘
        │                     │
        └────────────┬────────┘
                     │
        ┌────────────▼────────────────────┐
        │   main.py (CLI Orchestration)   │
        │  - Command routing              │
        │  - Task generation              │
        │  - Progress management          │
        └────┬──────────────┬─────────────┘
             │              │
    ┌────────▼──┐    ┌──────▼────────┐
    │   Config  │    │  Installer    │
    │  (utils)  │    │ (installers)  │
    │           │    │               │
    │ - Validate│    │ Strategy 1:   │
    │ - Parse   │    │ Scripts       │
    │ - Load OS │    │               │
    └────┬──────┘    │ Strategy 2:   │
         │           │ System Pkgs   │
         │           │               │
         │           │ Strategy 3:   │
         │           │ NPM Packages  │
         │           │               │
         │           │ Strategy 4:   │
         │           │ UV Tools      │
         │           └──────┬────────┘
         │                  │
         │    ┌─────────────┴──────────────┐
         │    │                            │
    ┌────▼────▼────────────────────┐   ┌──▼──────────┐
    │   concurrency.py             │   │ exceptions  │
    │   - ThreadPoolExecutor       │   │             │
    │   - TaskResult aggregation   │   │ Custom      │
    │   - Progress tracking        │   │ exceptions  │
    └────────┬─────────────────────┘   └─────────────┘
             │
    ┌────────▼──────────────┐
    │  Rich Progress Bars   │
    │  (User Feedback)      │
    └───────────────────────┘
```

---

## Command Flow Diagrams

### `tlc init` Flow
```
init command
    │
    └─ Create directory tree at {CODE_ROOT}/ (default: ~/code/, customize with TLC_CODE_DIR)
       ├─ venvs/
       ├─ oca/{version}/
       ├─ odoo/odoo/{version}/
       ├─ odoo/enterprise/{version}/
       └─ trobz/{projects, packages}/
        │
        └─ Display Rich tree
            └─ Exit 0
```

---

### `tlc pull-repos` Flow
```
pull-repos command
    │
    ├─ Load config.toml
    ├─ Validate config
    │
    ├─ Build task list:
    │   for each version:
    │     for each repo in config:
    │       if --filter && repo not in filter: skip
    │       create task: {name, func: _pull_repo, args: {repo, version, path}}
    │
    ├─ Show confirmation (newcomer mode)
    │   └─ If --dry-run: show preview, exit 0
    │
    ├─ Execute tasks in parallel (max 4 workers):
    │   for each task:
    │     if repo exists:
    │       git fetch origin {branch}
    │       git checkout {branch}
    │       git reset --hard origin/{branch}
    │     else:
    │       git clone --depth=1 --branch={branch} {url} {path}
    │     with GitProgress callback
    │
    ├─ Aggregate TaskResults
    └─ Report failures, exit 0 or 1
```

---

### `tlc install-tools` Flow
```
install-tools command
    │
    ├─ Load config.toml
    ├─ Validate config
    │
    ├─ Build installation preview:
    │   - Scripts: list URLs
    │   - System packages: list packages
    │   - NPM packages: list packages
    │   - UV tools: list tools
    │
    ├─ Show confirmation (newcomer mode)
    │   └─ If --dry-run: show preview, exit 0
    │
    ├─ Execute four installers in sequence:
    │   1. install_scripts()
    │       ├─ Create temp directory
    │       ├─ For each script:
    │       │   ├─ Download via wget or curl
    │       │   └─ Execute with /bin/sh
    │       └─ Clean up temp directory
    │
    │   2. install_system_packages()
    │       ├─ Detect OS (Arch, Ubuntu, macOS)
    │       ├─ Merge user packages with platform defaults
    │       ├─ Run package manager with sudo
    │       └─ Return success/failure boolean
    │
    │   3. install_npm_packages()
    │       ├─ Check if pnpm exists
    │       └─ Parallel: run_tasks() with pnpm install -g
    │
    │   4. install_uv_tools()
    │       └─ Parallel: run_tasks() with uv tool install
    │
    ├─ Aggregate all results
    └─ Report summary, exit 0 or 1
```

---

### `tlc create-venvs` Flow
```
create-venvs command
    │
    ├─ Load config.toml
    ├─ Validate config
    │
    ├─ Build task list:
    │   for each version:
    │     create task: {name: "venv-{version}", func: _create_venvs, ...}
    │
    ├─ Show confirmation (newcomer mode)
    │
    ├─ Execute tasks in parallel (max 4 workers):
    │   for each task:
    │     uv tool run odoo-venv --preset demo --python 3.12 {version}
    │     creates: ~/code/venvs/{version}/
    │
    ├─ Aggregate TaskResults
    └─ Report failures, exit 0 or 1
```

---

## Component Interaction Details

### Configuration Pipeline

```
{CODE_ROOT}/config.toml (default: ~/code/config.toml)
        │
        ▼
    [Read TOML]
    (tomli.loads)
        │
        ▼
    [Validate Structure]
    (Pydantic ConfigModel)
        │
        ├─ ConfigModel
        │   ├─ versions: list[str]
        │   ├─ tools: ToolsConfig
        │   └─ repos: RepoConfig
        │
        ├─ ToolsConfig
        │   ├─ uv: list[str]
        │   ├─ npm: list[str]
        │   ├─ script: list[ScriptItem]
        │   └─ system_packages: list[str]
        │
        └─ RepoConfig
            ├─ odoo: list[str]
            └─ oca: list[str]
        │
        ▼
    [Return Validated Dict]
    (get_config() in utils.py)
        │
        ▼
    [Main Commands Use Dict]
    (Generate tasks, installers)
```

---

### Task Execution Pipeline

```
Task Dict: {name, func, args}
    │
    ▼
[ThreadPoolExecutor]
(concurrency.run_tasks, max_workers=4)
    │
    ├─ Create Future for each task
    ├─ Provide Progress callback
    └─ Add to Rich progress bar
    │
    ▼
[Task Execution with Progress]
func(progress: Progress, task_id: TaskID, **args)
    │
    ├─ Success: TaskResult(name, success=True)
    │
    └─ Exception: TaskResult(name, success=False, error=...)
    │
    ▼
[Results Aggregation]
(list[TaskResult])
    │
    └─ Display summary with Rich
```

---

### Installer Strategy Pattern

```
install_tools request
        │
        ├─ Scripts
        │   ├─ Create temp directory
        │   ├─ For each URL:
        │   │   ├─ _get_download_command(url)
        │   │   │   ├─ Try wget (preferred)
        │   │   │   └─ Fall back to curl
        │   │   ├─ Execute download command
        │   │   └─ _execute_script(path)
        │   │       └─ Run with /bin/sh (safe)
        │   └─ Auto-cleanup temp directory
        │
        ├─ System Packages
        │   ├─ _get_package_manager_config(os, distro)
        │   │   ├─ Arch → pacman -S --noconfirm --needed
        │   │   ├─ Ubuntu → apt-get install -y
        │   │   └─ macOS → brew install
        │   ├─ Merge user packages with defaults
        │   └─ _run_package_install(cmd, packages)
        │       └─ Execute with sudo
        │
        ├─ NPM Packages
        │   ├─ Check: which pnpm
        │   ├─ For each package:
        │   │   └─ pnpm install -g {package}
        │   └─ Parallel via run_tasks()
        │
        └─ UV Tools
            ├─ For each tool:
            │   └─ uv tool install -- {tool}
            └─ Parallel via run_tasks()
```

---

## Error Handling Architecture

```
[Error Detection Point]
        │
        ├─ Configuration Error
        │   └─ Pydantic ValidationError
        │       ├─ Print field-level errors
        │       ├─ Show example config
        │       └─ Exit 1
        │
        ├─ Prerequisite Missing
        │   └─ ExecutableNotFoundError(executable)
        │       ├─ Record in TaskResult
        │       ├─ Continue other tasks
        │       └─ Fail at end if any error
        │
        ├─ Task Exception
        │   └─ Custom exception
        │       ├─ Catch and record
        │       ├─ Continue in parallel
        │       └─ Show ✗ Error in progress
        │
        └─ User Interrupt
            └─ KeyboardInterrupt
                ├─ Cancel running futures
                ├─ Cleanup resources
                └─ Exit gracefully
```

---

## Concurrency Model

### Worker Pool
- **Type**: ThreadPoolExecutor
- **Max Workers**: 4 (configurable)
- **Rationale**: I/O-bound tasks (downloads, git, package installation)
- **Not suitable for**: CPU-intensive tasks

### Task Isolation
```
Worker 1: Git clone repo-1
Worker 2: Git clone repo-2
Worker 3: Git fetch repo-3
Worker 4: Git checkout repo-4

If Worker 1 fails:
  - TaskResult(name="repo-1", success=False, error=...)
  - Workers 2, 3, 4 continue
  - Final exit code: 1 (any failure)
```

### Progress Aggregation
```
Rich Progress Bar (one per task)
├─ Task: "repo-1"
│   ├─ Status: [████████░░░░░░░░░░░░] 45%
│   └─ Message: "Fetching objects..."
│
├─ Task: "repo-2"
│   ├─ Status: [██████████████████░░░] 95%
│   └─ Message: "Writing objects..."
│
└─ Task: "repo-3"
    ├─ Status: [██████████████████████] 100% ✓
    └─ Message: "Complete"
```

---

## Platform Detection & Configuration

```
[get_os_info()]
        │
        ├─ Darwin (macOS)
        │   └─ system: "Darwin"
        │       distro: "macos"
        │
        └─ Linux
            ├─ Try freedesktop_os_release()
            │   ├─ Arch Linux → distro: "arch"
            │   ├─ Ubuntu → distro: "ubuntu"
            │   └─ Other → distro: "linux"
            │
            └─ Fallback → system: "unknown"

[get_package_manager_config(system, distro)]
        │
        ├─ macOS → brew
        ├─ Arch → pacman
        ├─ Ubuntu → apt-get
        └─ Fallback error
```

---

## Data Structures

### TaskResult
```python
@dataclass
class TaskResult:
    name: str                    # Task identifier ("repo-1", "tool-x", etc.)
    success: bool                # True if completed, False if exception
    message: str | None = None   # Status message ("Completed", error summary)
    error: Exception | None = None # Exception object if failed
```

### Task Dict
```python
{
    "name": "string",                    # Identifier for display
    "func": callable,                    # Function to execute
    "args": {                            # Keyword arguments (optional)
        "repo": "repo_name",
        "version": "16.0",
        "path": "/home/user/code/oca/repo_name"
    }
}
```

### Pydantic Models (utils.py)
```python
ConfigModel(
    versions: list[str],
    tools: ToolsConfig | None,
    repos: RepoConfig | None
)

ToolsConfig(
    uv: list[str] | None,
    npm: list[str] | None,
    script: list[ScriptItem] | None,
    system_packages: list[str] | None
)

ScriptItem(
    url: str,        # HTTPS enforced
    name: str | None # Optional display name
)

RepoConfig(
    odoo: list[str] | None,
    oca: list[str] | None
)
```

---

## Security Boundaries

### Trust Model
```
User (trusted)
    │
    ▼
{CODE_ROOT}/config.toml (default: ~/code/config.toml, semi-trusted, validated)
    │
    ├─ Pydantic validation
    ├─ Regex pattern validation
    └─ HTTPS enforcement for URLs
    │
    ▼
External Resources (untrusted)
    │
    ├─ Git repositories
    ├─ Shell scripts
    ├─ NPM packages
    └─ UV tools
```

### Execution Safety
```
Script Execution
    │
    ├─ Subprocess safety: no shell=True
    ├─ Full paths: shutil.which() instead of PATH
    ├─ Argument lists: never string concatenation
    └─ Temp directory: auto-cleanup
```

---

## Extension Points

### Adding New Commands
1. Define function in `main.py` with `@app.command()` decorator
2. Follow signature: `func(ctx: typer.Context, ...)` with typer.Option() for additional parameters
3. Use `confirm_step()` for newcomer mode
4. Call installers or utilities as needed
5. Return `typer.Exit(code=0)` on success or `typer.Exit(code=1)` on failure

### Adding New Installers
1. Create function: `install_xxx(items: list[str], dry_run: bool) -> list[TaskResult]`
2. Use `run_tasks()` for parallelization with `max_workers` parameter
3. Add to `_run_installers()` in main.py

### Adding Configuration Fields
1. Update Pydantic models in `utils.py`
2. Add validators if needed (regex patterns, custom logic)
3. Document in `docs/project-overview-pdr.md`

### Concurrency Configuration
- `run_tasks()` accepts `max_workers` parameter (default: 4)
- Can be customized per operation type if needed
- Example: `run_tasks(tasks, max_workers=8)` for more parallelization

---

## Performance Characteristics

### Typical Execution Times
- **init**: < 1 second (local filesystem only)
- **pull-repos** (1 repo): 10-30 seconds (network dependent)
- **pull-repos** (5 repos parallel): 15-40 seconds (vs 50-150 sequential)
- **install-tools** (all types): 5-15 minutes (highly variable, depends on tools)
- **create-venvs** (4 versions parallel): 10-20 minutes (vs 40-80 sequential)

### Parallelization Impact
- 4 concurrent git clones ≈ 3x faster than sequential
- 4 concurrent venv creations ≈ 3-3.5x faster than sequential
- System package install remains sequential (sudo, package manager serialization)

---

## Deployment Model

### Installation
```bash
uv tool install git+ssh://git@github.com:trobz/local.py.git
```
- Installs to user's Python tool directory
- Creates `tlc` entry point
- Self-contained, no global state

### Configuration
```bash
# User creates once:
~/code/config.toml  # or {TLC_CODE_DIR}/config.toml
```
- Personal environment definition
- Not committed to any repository
- Can vary per developer
- Config location follows the code root directory

### Execution
```bash
tlc <command>  # Works from anywhere
```
- Uses `TLC_CODE_DIR` env var if set, otherwise `$HOME/code/` as root
- No elevated privileges needed except for package installation (sudo)
- All changes isolated to user's home directory
- Customize with: `export TLC_CODE_DIR=/custom/path`
