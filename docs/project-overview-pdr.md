# Project Overview & Product Requirements

## Overview

`trobz_local` (CLI: `tlc`) is a developer automation tool for setting up and managing local Odoo development environments. It reduces setup time from hours to minutes by automating directory creation, repository management, and tool installation.

The tool uses declarative configuration: developers specify desired environment state in `{CODE_ROOT}/config.toml` (default: `~/code/config.toml`), and `tlc` performs necessary operations to reach that state. The code root can be customized via the `TLC_CODE_DIR` environment variable.

## Vision & Purpose

**Problem Solved**: Odoo developers spend significant time on environment setup tasks (directory creation, git operations, virtual environments, dependencies). This is repetitive, error-prone, and inconsistent across team members.

**Solution**: Single declarative configuration file with automated, parallelized execution ensures consistent, reproducible environments.

**Success Metric**: Setup time reduced from hours to under 15 minutes. All developers on a team have identical directory structures and tool versions.

## Target Users

- **Primary**: Odoo developers at Trobz
- **Secondary**: Teams developing multiple Odoo versions (16.0, 17.0, 18.0+)
- **Onboarding**: New developers joining Odoo projects

## Core Features

### 0. Bootstrap Script (`bootstrap.sh`)
Automated installation of prerequisites before using `tlc`:
- **Dependencies**: Installs git, gh (GitHub CLI), and uv
- **SSH Setup**: Configures GitHub SSH keys in known_hosts
- **Installation**: Installs `trobz_local` CLI (tlc) via uv
- **Idempotent**: Skips already-installed tools
- **OS-aware**: Supports macOS (brew), Debian/Ubuntu (apt), Fedora (dnf), Arch (pacman)

**Usage**:
```bash
curl -fsSL https://raw.githubusercontent.com/trobz/local.py/main/bootstrap.sh | sh
```

After bootstrap, use `tlc` commands to complete environment setup.

---

### 1. Environment Initialization (`init`)
Creates standardized directory structure (default: `~/code/`):
```
{CODE_ROOT}/
├── venvs/           # Python virtual environments
├── oca/             # OCA repositories (Odoo Community Association)
├── odoo/            # Odoo repositories
│   ├── odoo/        # Source code by version
│   └── enterprise/  # Enterprise code by version
└── trobz/           # Internal Trobz repositories
    ├── projects/
    └── packages/
```

Use `TLC_CODE_DIR` environment variable to customize the base directory.

### 2. Repository Management (`pull-repos`)
Clones or updates Odoo and OCA repositories:
- **Sources**: Official Odoo repos and OCA GitHub repos
- **Speed**: Shallow clones (depth=1) by default for bandwidth efficiency
- **Full History**: Use `--full-history` flag to fetch complete commit history
- **Parallelization**: Multiple repos cloned/updated simultaneously
- **Operations**: Clone new repos, fetch and hard-reset existing ones

### 3. Tool Installation (`install-tools`)
**Five-stage installation pipeline**:
1. **PostgreSQL Repository** (Debian/Ubuntu only): Setup PGDG APT repository with GPG verification (idempotent)
2. **Shell Scripts**: Download and execute scripts (e.g., uv installer)
3. **System Packages**: OS-aware installation via apt/pacman/brew (runs after PostgreSQL repo setup on Debian/Ubuntu)
4. **NPM Packages**: Global packages via npm
5. **UV Tools**: Python tools via uv tool install

### 4. Virtual Environment Management (`create-venvs`)
Creates Odoo-specific environments:
- Uses `odoo-venv` tool via UV
- Parallelized creation for multiple versions
- Preset: demo, Python: 3.12

### 5. PostgreSQL User Management (`ensure-db-user`)
Verify or create PostgreSQL user for Odoo development:
- Checks PostgreSQL availability via `pg_isready`
- Verifies "odoo" user exists with CREATEDB permission
- Creates user if missing (hardcoded credentials: odoo/odoo for dev-only)
- OS-aware execution (Linux: sudo -u postgres | macOS: direct access)
- Connection testing with created credentials
- Security: Input validation, SQL injection prevention via psql variable binding

### 6. Interactive Mode
**Newcomer Mode** (default enabled, can disable with `--newcomer=false`):
- Confirmation prompts before operations
- Detailed messages explaining actions
- Helps new developers understand workflow
- Can be disabled via flag or `NEWCOMER_MODE` environment variable

### 7. Security
- HTTPS-only enforcement for script downloads
- No shell injection vulnerabilities (no shell=True)
- Subprocess safety with explicit executable paths
- Configuration validation via Pydantic
- SQL injection prevention via psql variable binding (ensure-db-user)
- Input validation for PostgreSQL identifiers (usernames)

## Functional Requirements

| Requirement | Description |
|---|---|
| **FR-1: Directory Structure** | Create `{CODE_ROOT}/` (default: `~/code/`) with `venvs/`, `oca/`, `odoo/`, `trobz/` subdirectories and version-specific folders |
| **FR-2: Repository Operations** | Clone repos with `depth=1`, update via fetch+reset, support parallelization, allow name filtering |
| **FR-3: Virtual Environments** | Create venvs for each Odoo version using `odoo-venv`, support parallel creation |
| **FR-4: Tool Installation** | Five-stage pipeline: PostgreSQL repo → scripts → system packages → npm → uv tools; OS-aware package managers |
| **FR-5: PostgreSQL User** | Verify/create PostgreSQL "odoo" user with CREATEDB permission; OS-aware execution (Linux sudo, macOS direct); connection validation |
| **FR-6: Configuration** | TOML config at `{CODE_ROOT}/config.toml` (default: `~/code/config.toml`), strict Pydantic validation, clear error messages with examples |
| **FR-7: User Interaction** | Interactive "newcomer mode", dry-run preview, rich console UI (progress bars, trees, colors) |

## Non-Functional Requirements

| Requirement | Details |
|---|---|
| **NFR-1: Performance** | Default 4-worker thread pool for parallel tasks; shallow clones for bandwidth efficiency |
| **NFR-2: Security** | HTTPS-only downloads; no shell injection (no shell=True); explicit executable paths |
| **NFR-3: Compatibility** | Python 3.10+; Linux (Arch, Ubuntu) and macOS; WSL experimental/untested |
| **NFR-4: Reliability** | Task isolation: failures don't block others; exit 1 if any task fails; graceful KeyboardInterrupt |

## Success Metrics

- **Setup Time**: Reduce full environment setup from hours to under 15 minutes
- **Consistency**: All team developers have identical directory structures and tool versions
- **Usability**: Newcomers complete setup following interactive prompts with minimal external guidance
- **Reliability**: Tool handles errors gracefully with clear messages and recoverable states

## Configuration Schema

### Basic Example

```toml
versions = ["16.0", "17.0", "18.0"]

[tools]
uv = ["odoo-venv", "odoo-addons-path", "pre-commit"]
npm = ["prettier", "eslint"]
system_packages = ["git", "postgresql"]

[repos]
odoo = ["odoo", "enterprise"]
oca = ["server-tools", "server-ux", "web"]
```

### Field Reference & Validation

#### `versions` (Required)
Odoo versions to set up. Supports semantic versioning (Major.Minor) or "master" branch.
- **Type**: List of strings
- **Pattern**: `^(?:\d+\.\d+|master)$`
- **Examples**: `["16.0", "17.0", "18.0"]` or `["master", "17.0"]`
- **Note**: "master" branch for development, semver (16.0, 17.0) for stable releases

#### `tools.uv` (Optional)
UV tools to install globally via `uv tool install`
- **Type**: List of strings
- **Pattern**: `^[a-zA-Z0-9][a-zA-Z0-9._\-\[\]@=<>!,]*$`
- **Supports**: Pip-style specifiers (e.g., `package[extra]@1.0`, `package>=1.0`)
- **Examples**: `["odoo-venv", "pre-commit", "black[d]>=24.0"]`

#### `tools.npm` (Optional)
NPM packages to install globally via npm
- **Type**: List of strings
- **Pattern**: `^(@[a-z0-9-~][a-z0-9-._~]*/)?[a-z0-9-~][a-z0-9-._~]*$`
- **Supports**: Scoped (@org/package) and unscoped packages
- **Examples**: `["prettier", "@babel/core", "eslint"]`

#### `tools.script` (Optional)
Shell scripts to download and execute
- **Type**: List of objects
- **Fields**:
  - `url` (required): HTTPS URL only (enforced)
  - `name` (optional): Display name for logging
- **Example**:
  ```toml
  [[tools.script]]
  url = "https://example.com/install.sh"
  name = "my installer"
  ```

#### `tools.system_packages` (Optional)
System packages to install via OS-specific manager
- **Type**: List of strings
- **Merged with**: Platform-specific defaults (see table below)
- **Examples**: `["postgresql", "git", "libxml2"]`

#### `repos.odoo` (Optional)
Official Odoo repositories to clone
- **Type**: List of strings
- **Pattern**: `^[a-zA-Z0-9._-]+$`
- **Valid values**: `"odoo"` (source code), `"enterprise"` (proprietary)
- **URL bases**: `git@github.com:odoo/{repo_name}.git`

#### `repos.oca` (Optional)
Odoo Community Association repositories to clone
- **Type**: List of strings
- **Pattern**: `^[a-zA-Z0-9._-]+$`
- **URL base**: `git@github.com:OCA/{repo_name}.git`
- **Examples**: `"server-tools"`, `"web"`, `"server-ux"`

### Platform-Specific Defaults

System packages are automatically merged with defaults for your OS:

| OS | Default Packages |
|---|---|
| **Arch** | gcc, postgresql, libxml2, libxslt, libjpeg, libsass, base-devel, git |
| **Ubuntu** | git, gcc, libsasl2-dev, libldap2-dev, libssl-dev, libffi-dev, libxml2-dev, libxslt1-dev, libjpeg-dev, libpq-dev, libsass-dev, postgresql, postgresql-client, postgresql-contrib |
| **macOS** | git, postgresql, node |

### Validation Examples

**Valid configurations:**
```toml
versions = ["16.0", "17.0", "master"]         # ✓ Correct format with master branch
tools.uv = ["package[extra]@1.0", "tool"]     # ✓ Supports extras syntax
tools.npm = ["@babel/core", "prettier"]       # ✓ Scoped and unscoped
repos.odoo = ["odoo", "enterprise"]           # ✓ Both sources
repos.oca = ["server-tools", "web"]           # ✓ Valid names
```

**Invalid configurations:**
```toml
versions = ["16", "17.0"]                      # ✗ First version invalid (missing minor)
versions = ["main", "17.0"]                    # ✗ "main" not supported (use "master")
tools.uv = [" invalid"]                        # ✗ Leading space
tools.npm = ["__invalid"]                      # ✗ Double underscore
tools.script = [{url = "http://..."}]          # ✗ HTTP not allowed (HTTPS only)
repos.odoo = ["invalid/name"]                  # ✗ Slash not allowed
```

## CLI Command Reference

### `tlc init`
Initialize the directory structure (default: `~/code/`, customize with `TLC_CODE_DIR`).

**Usage**: `tlc init`

**Options**:
- `--newcomer / --no-newcomer`: Enable interactive mode (default: True)

**Environment Variables**:
- `TLC_CODE_DIR`: Override default `~/code` base directory

**Output**: Rich tree showing created directory structure

**Exit Codes**: 0 on success, 1 on failure

---

### `tlc pull-repos`
Clone missing repositories and update existing ones.

**Usage**: `tlc pull-repos [OPTIONS]`

**Options**:
- `-f, --filter`: Filter repositories by name (repeatable, e.g., `-f server-tools -f web`)
- `--dry-run`: Preview operations without executing
- `--full-history`: Fetch full commit history instead of shallow clone (depth=1)
- `--newcomer / --no-newcomer`: Enable interactive mode (default: True)

**Behavior**:
- Reads `{CODE_ROOT}/config.toml` (default: `~/code/config.toml`) and loads repo definitions
- For each version, clones missing repos (shallow, depth=1 by default) or updates existing ones
- Updates via: git fetch, checkout branch, hard reset to origin/branch
- Executes up to 4 repos in parallel
- Uses GitProgress for progress reporting

**Examples**:
```bash
# Shallow clone (default, faster, less bandwidth)
tlc pull-repos

# Full clone (complete commit history)
tlc pull-repos --full-history

# Filter specific repos with full history
tlc pull-repos --filter odoo --full-history
```

**When to use --full-history**:
- Need to browse full git history
- Performing git bisect operations
- Analyzing commit patterns over time
- Contributing patches based on historical context

**Default behavior (depth=1)**:
- Faster downloads (less data transferred)
- Smaller disk usage
- Sufficient for most development workflows
- Can be "unshallowed" later with `git fetch --unshallow`

**Exit Codes**: 0 on success, 1 if any repo operation fails

---

### `tlc create-venvs`
Create Python virtual environments for each Odoo version.

**Usage**: `tlc create-venvs [OPTIONS]`

**Options**:
- `--newcomer / --no-newcomer`: Enable interactive mode (default: True)

**Behavior**:
- Reads versions from `{CODE_ROOT}/config.toml` (default: `~/code/config.toml`)
- Invokes `uv tool run odoo-venv --preset demo --python 3.12` for each version
- Creates venvs at `{CODE_ROOT}/venvs/{version}/` (default: `~/code/venvs/{version}/`)
- Executes up to 4 venvs in parallel
- Shows progress bar during creation

**Prerequisites**: `odoo-venv` must be installed (via `tlc install-tools`)

**Exit Codes**: 0 on success, 1 if any venv creation fails

---

### `tlc install-tools`
Install tools from five sources in order: PostgreSQL repo, scripts, system packages, npm, uv.

**Usage**: `tlc install-tools [OPTIONS]`

**Options**:
- `--dry-run`: Preview without executing
- `--newcomer / --no-newcomer`: Enable interactive mode (default: True)

**Execution Order**:
1. **PostgreSQL Repository** (Debian/Ubuntu): Setup PGDG APT repository with GPG verification
2. **Scripts**: Download and execute via `wget` or `curl`, then `sh`
3. **System Packages**: OS-aware installation (apt/pacman/brew) - runs after PostgreSQL repo on Debian/Ubuntu
4. **NPM Packages**: Global installation via `npm install -g`
5. **UV Tools**: Global installation via `uv tool install`

**Behavior**:
- Reads `[tools]` section from `{CODE_ROOT}/config.toml` (default: `~/code/config.toml`)
- Shows descriptive message of all tools to be installed
- Confirms in newcomer mode
- Scripts and NPM/UV tools run in parallel (max 4 workers)
- System packages run sequentially (sudo required)
- Aggregates results and reports failures

**Exit Codes**: 0 on success, 1 if any tool installation fails

---

### `tlc ensure-db-user`
Verify or create PostgreSQL user "odoo" for Odoo development.

**Usage**: `tlc ensure-db-user`

**Behavior**:
- Checks if PostgreSQL is running on localhost via `pg_isready`
- Verifies PostgreSQL user "odoo" exists
- Creates user with CREATEDB permission if missing (hardcoded dev credentials)
- Tests connection with created user
- OS-aware execution:
  - **Linux**: Executes as `postgres` user via `sudo -n -u postgres`
  - **macOS**: Direct execution (PostgreSQL via Homebrew runs as current user)

**Security**:
- Input validation for PostgreSQL identifiers (max 63 chars, alphanumeric + underscore)
- SQL injection prevention via psql variable binding (`:\"username\"` for identifiers, `:'password'` for values)
- Secure environment variable handling for credentials

**Exit Codes**:
- `0` - User ready for Odoo development
- `1` - PostgreSQL not running
- `2` - Sudo authentication failed (Linux)
- `3` - User creation failed or connection test failed

**Prerequisites**:
- PostgreSQL server running on localhost
- `pg_isready` and `psql` installed
- On Linux: user must have passwordless sudo access to postgres user

**Security Warning**: Uses hardcoded dev-only credentials (odoo:odoo). Never use in production.

---

### Global Options

**`--newcomer / --no-newcomer`** (all commands)
- **Default**: True
- **Environment Variable**: `NEWCOMER_MODE=true/false`
- **Behavior**:
  - Enabled: Shows confirmation prompts with detailed action descriptions
  - Disabled: Executes silently without prompts
- **Use case**: Disable with `--no-newcomer` or `NEWCOMER_MODE=false` after becoming familiar

**Examples**:
```bash
tlc pull-repos --no-newcomer      # Silent mode
NEWCOMER_MODE=false tlc init      # Via environment variable
tlc install-tools --dry-run       # Preview operations
```

---

### Environment Variables

| Variable | Default | Affects |
|---|---|---|
| `NEWCOMER_MODE` | true | Interactive mode for all commands |
| `HOME` | (user home) | Used to resolve `~/code` default path |
| `TLC_CODE_DIR` | `~/code` | Override the default code root directory |

---

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Configuration error, validation failure, or operation failure |
