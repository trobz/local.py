# trobz_local (tlc)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-lightgrey.svg)](https://www.gnu.org/licenses/agpl-3.0)

A developer tool for automating setup and management of local Odoo development environments. Streamlines directory structure creation, source code repository management, and installation of required development tools.

## What is trobz_local?

`trobz_local` (CLI: `tlc`) automates repetitive tasks when setting up an Odoo development environment. Instead of manually creating directories, cloning repositories, and installing dependencies, developers declare their desired environment in a TOML configuration file and `tlc` handles the rest.

## Key Features

- **Environment Initialization** (`init`): Creates standardized directory structure at `~/code/`
- **Repository Management** (`pull-repos`): Clones/updates Odoo and OCA repos in parallel
- **Tool Installation** (`install-tools`): Installs from four sources: scripts, system packages, NPM, and UV tools
- **Virtual Environments** (`create-venvs`): Creates Odoo venvs for each configured version
- **Interactive Mode**: Newcomer mode with confirmations and guidance
- **Security**: HTTPS enforcement for all downloads

## Installation

Install globally using [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+ssh://git@github.com:trobz/local.py.git
```

## Quick Start

```bash
# 1. Initialize directory structure
tlc init

# 2. Create config file
cat > ~/code/config.toml << 'EOF'
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
| `tlc init` | Create directory structure in `~/code/` |
| `tlc pull-repos` | Clone or update Odoo/OCA repositories |
| `tlc create-venvs` | Create Python virtual environments |
| `tlc install-tools` | Install scripts, packages, and tools |

Use `--newcomer=false` to skip confirmation prompts. Use `--help` on any command for options.

## Configuration

Place `~/code/config.toml` with your environment definition:

```toml
versions = ["16.0", "17.0", "18.0"]

[tools]
uv = ["odoo-venv", "odoo-addons-path", "pre-commit"]
npm = ["prettier", "eslint"]
system_packages = ["git", "postgresql", "pnpm"]

[[tools.script]]
url = "https://astral.sh/uv/install.sh"
name = "uv installer"

[repos]
odoo = ["odoo", "enterprise"]
oca = ["server-tools", "server-ux", "web"]
```

See [Configuration Schema](./docs/project-overview-pdr.md#configuration-schema) for all options and validation rules.

## System Requirements

- Python 3.10+
- `uv` package manager
- Linux (Arch, Ubuntu) or macOS
- System tools: `git`, `wget` or `curl`, `sh`

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
