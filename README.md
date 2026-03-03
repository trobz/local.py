# trobz_local (tlc)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-lightgrey.svg)](https://www.gnu.org/licenses/agpl-3.0)

A developer tool for automating setup and management of local Odoo development environments. Streamlines directory structure creation, source code repository management, and installation of required development tools.

## What is trobz_local?

`trobz_local` (CLI: `tlc`) automates repetitive tasks when setting up an Odoo development environment. Instead of manually creating directories, cloning repositories, and installing dependencies, developers declare their desired environment in a TOML configuration file and `tlc` handles the rest.

## Key Features

- **Environment Initialization** (`init`): Creates standardized directory structure (default: `~/code/`)
- **Repository Management** (`pull-repos`): Clones/updates Odoo and OCA repos in parallel
- **Tool Installation** (`install-tools`): Installs from four sources: scripts, system packages, NPM, and UV tools
- **Virtual Environments** (`create-venvs`): Creates Odoo venvs for each configured version
- **Interactive Mode**: Newcomer mode with confirmations and guidance
- **Security**: HTTPS enforcement for all downloads
- **Custom Directory**: Use `TLC_CODE_DIR` env var to override default `~/code` location

## Installation

### Quick Install (Recommended)

Run the bootstrap script to install all dependencies and `tlc` in one command:

```bash
curl -fsSL https://raw.githubusercontent.com/trobz/local.py/main/bootstrap.sh | bash
```

This installs: `git`, `gh`, `uv`, configures PostgreSQL APT repository, and sets up SSH for GitHub.

### Manual Install

If you already have `uv` installed:

```bash
uv tool install git+https://github.com/trobz/local.py.git
```

## Quick Start

```bash
# 1. Initialize directory structure (uses ~/code by default, or set TLC_CODE_DIR)
export TLC_CODE_DIR=~/Development  # Optional: customize location
tlc init

# 2. Create config file
cat > ~/Development/config.toml << 'EOF'
versions = ["16.0", "17.0"]

[tools]
uv = ["odoo-venv", "pre-commit"]
npm = ["prettier"]
system_packages = ["postgresql"]

[repos]
odoo = ["odoo", "enterprise"]
oca = ["server-tools"]
EOF

# 3. Setup environment
tlc pull-repos       # Clone repositories
tlc create-venvs     # Create virtual environments
tlc install-tools    # Install tools
```

## Commands

| Command | Purpose |
|---------|---------|
| `tlc init` | Create directory structure (default: `~/code/`) |
| `tlc pull-repos` | Clone or update Odoo/OCA repositories |
| `tlc create-venvs` | Create Python virtual environments |
| `tlc install-tools` | Install scripts, packages, and tools |

Use `--newcomer=false` to skip confirmation prompts. Use `--help` on any command for options.

## Configuration

Place `config.toml` in your code directory (default: `~/code/config.toml`):

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

### Custom Code Directory

By default, `tlc` uses `~/code` as the base directory. You can customize this by setting the `TLC_CODE_DIR` environment variable:

```bash
# Use a custom directory
export TLC_CODE_DIR=/data/dev
tlc init  # Creates directory structure at /data/dev

# One-liner
TLC_CODE_DIR=/custom/path tlc init
```

The config file will be created at `{TLC_CODE_DIR}/config.toml`.

See [Configuration Schema](./docs/project-overview-pdr.md#configuration-schema) for all options and validation rules.

## System Packages

When `install-tools` installs system packages, it uses a curated list that goes beyond what Odoo itself requires. The goal is to pre-install all system-level dependencies needed to compile and run any OCA module out of the box — things like `libcups2-dev` (for `pycups`), `libgeos-dev` (for `shapely`), `libxmlsec1-dev` (for `pysaml2`), `libzbar-dev` (for `pyzbar`), and more. This avoids compilation errors when installing OCA module requirements, without needing to know in advance which modules will be used.

## System Requirements

- Python 3.10+
- Linux (Arch, Ubuntu) or macOS
- `curl`
- Sudo privileges (for bootstrap script)

## Documentation

For detailed information:

- [**Project Overview & PDR**](./docs/project-overview-pdr.md): Features, requirements, configuration schema
- [**System Architecture**](./docs/system-architecture.md): Design patterns, component interactions
- [**Codebase Summary**](./docs/codebase-summary.md): Module-by-module technical details
- [**Code Standards**](./docs/code-standards.md): Development guidelines and conventions

## Development

```bash
git clone git@github.com:trobz/local.py.git && cd local.py
uv sync && uv run pre-commit install
make check  # Linters and type checks
make test   # Run tests
```

## License

AGPL-3.0 - See [LICENSE](./LICENSE) for details.
