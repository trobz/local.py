# Project Roadmap

High-level development phases, milestones, and project status for `trobz_local` (tlc).

## Current Status

| Item | Status |
|------|--------|
| **Current Version** | 0.7.0 |
| **Current Branch** | main (stable) |
| **Development Branch** | feat/doctor-command (merged) |
| **Release Cycle** | Semantic versioning with conventional commits |

## Project Phases

### Phase 1: Core Features (Complete - v0.1.0 to v0.6.0)

**Objective**: Deliver essential automation for Odoo dev environment setup.

**Features Delivered**:
1. **Environment Initialization** (`init`) - v0.1.0
   - Creates standardized directory structure
   - Customizable via `TLC_CODE_DIR` environment variable
   - Status: Complete and stable

2. **Repository Management** (`pull-repos`) - v0.1.0
   - Clone/update Odoo and OCA repositories
   - Shallow cloning for efficiency (depth=1)
   - Parallel execution (4 workers)
   - Filter and dry-run support
   - Status: Complete and stable

3. **Tool Installation** (`install-tools`) - v0.2.0 to v0.6.0
   - Five-stage pipeline: PostgreSQL repo → scripts → system packages → NPM → UV
   - OS-aware installation (Linux/macOS, distro-specific)
   - PostgreSQL APT repository setup (v0.6.0)
   - Parallel script and tool execution
   - Status: Complete and stable

4. **Virtual Environment Management** (`create-venvs`) - v0.3.0 to v0.6.0
   - Create Odoo-specific venvs via odoo-venv tool
   - Parallel creation (4 workers)
   - Launcher script creation option (v0.6.0)
   - Status: Complete and stable

5. **PostgreSQL User Setup** (`ensure-db-user`) - v0.4.0 to v0.6.0
   - User verification and creation
   - OS-aware execution (sudo on Linux, direct on macOS)
   - Connection testing
   - Security: SQL injection prevention, input validation
   - Status: Complete and stable

6. **Interactive User Experience** (v0.1.0 to v0.5.0)
   - Newcomer mode with confirmation prompts
   - Dry-run preview mode
   - Rich console UI (progress bars, colors, trees)
   - Status: Complete and stable

7. **Environment Diagnostics** (`doctor`) - v0.7.0
   - Health checks: config validity, GitHub SSH, tool versions, venvs
   - CheckStatus enum (OK/WARN/FAIL) with detailed reporting
   - Rich table output grouped by category
   - Exit code reflects check results (0 if all OK, 1 if any FAIL)
   - Status: Complete and stable

### Phase 2: Enhancement & Maintenance (In Progress)

**Objective**: Expand functionality and maintain high code quality.

#### Future Enhancements
- [ ] Configuration profile support (multiple named environments)
- [ ] Project template system (quick-start templates per project type)
- [ ] Cloud storage integration for config backup
- [ ] Windows/WSL support (currently Linux/macOS only)
- [ ] Tool version pinning in config
- [ ] Advanced filtering for parallel tasks

## Version History

| Version | Date | Major Changes |
|---------|------|---|
| **0.7.0** | Mar 2025 | `doctor` command for environment diagnostics (config, SSH, tools, venvs) |
| **0.6.0** | Jan 2025 | PostgreSQL APT repo setup, create_launcher option, --yes flag, improved documentation |
| **0.5.0** | Jan 2025 | Enhanced error handling, security improvements, testing suite |
| **0.4.0** | 2024 | PostgreSQL user management (ensure-db-user) |
| **0.3.0** | 2024 | Virtual environment creation with odoo-venv |
| **0.2.0** | 2024 | Tool installation (scripts, system packages, NPM, UV) |
| **0.1.0** | 2024 | Initial release: init, pull-repos, basic structure |

## Milestones

### Completed Milestones

- ✓ **M1**: Core CLI framework (init, pull-repos)
- ✓ **M2**: Tool installation pipeline
- ✓ **M3**: Virtual environment management
- ✓ **M4**: PostgreSQL integration
- ✓ **M5**: Security hardening (HTTPS, SQL injection prevention)
- ✓ **M6**: Enhanced user experience (newcomer mode, dry-run)
- ✓ **M7**: Comprehensive test coverage (982 LOC of tests)
- ✓ **M8**: Documentation (API, architecture, standards)

### Active Milestones

- ✓ **M9**: Doctor command (diagnostics/verification)
  - Status: Complete in v0.7.0
  - Implemented: Health checks (config, SSH, tools, venvs), CheckStatus enum, Rich table output

### Future Milestones

- 🔄 **M10**: Configuration profiles (multiple named environments)
- 🔄 **M11**: Project templates (quick-start setup)
- 🔄 **M12**: Windows/WSL support

## Success Metrics

| Metric | Target | Current Status |
|--------|--------|---|
| **Setup time** | < 15 minutes full environment | ✓ Achieved |
| **Test coverage** | > 80% | ✓ ~87% (1006/1674 LOC) |
| **Documentation** | All features documented | ✓ Complete |
| **Security** | No shell injection, HTTPS-only | ✓ Enforced |
| **Compatibility** | Python 3.10+, Linux/macOS | ✓ Verified |
| **Reliability** | Graceful error handling | ✓ Implemented |

## Development Activities

### Recent Work

- **v0.6.0**: PostgreSQL repository setup, create_launcher option, --yes flag for automation
- **v0.5.0**: Error handling improvements, test suite expansion
- **Testing**: 982 LOC of unit tests covering core functionality

### Current Work

- **feat/doctor-command**: New `doctor` command for environment validation
  - Diagnostics for Python venvs, PostgreSQL, tools, configuration
  - Better visibility into environment issues

### Known Limitations

- **Windows/WSL**: Not officially supported (Linux/macOS only)
- **Configuration profiles**: Single config file per code root
- **Tool pinning**: No version pinning in config (uses latest)
- **Offline mode**: Requires network access for initial setup

## Technical Debt

- [ ] Consider splitting main.py if it grows beyond 600 LOC
- [ ] Performance optimization for large repos (>100 repos)
- [ ] Enhanced error recovery for network failures

## Dependencies

### Runtime Dependencies
- **typer**: >= 0.20 (CLI framework)
- **pydantic**: >= 2.12.5 (configuration validation)
- **gitpython**: >= 3.1.45 (git operations)
- **rich**: (progress bars, UI)
- **tomli**: >= 2.3.0 (TOML parsing for Python < 3.11)

### Development Dependencies
- **pytest**: >= 7.2.0 (testing)
- **ruff**: >= 0.11.5 (linting/formatting)
- **pre-commit**: >= 2.20.0 (git hooks)
- **python-semantic-release**: >= 10.5.3 (versioning)

## Support & Maintenance

### Release Schedule
- **Semantic Versioning**: MAJOR.MINOR.PATCH
- **Conventional Commits**: Enforced for automatic versioning
- **Pre-commit Hooks**: Linting and type checking before commits
- **Automated Testing**: CI/CD pipeline on GitHub

### Backward Compatibility
- Configuration schema remains stable across minor versions
- Breaking changes documented in release notes
- Migration guides provided for major version updates

## Contributing Guidelines

See [Code Standards](./code-standards.md) for:
- File structure and naming conventions
- Code style and security requirements
- Testing and documentation standards
- Commit message format

### Branch Strategy
- **main**: Stable, released code
- **feat/{feature-name}**: Feature development
- **fix/{issue-name}**: Bug fixes
- All changes require pull requests with tests

## Contact & Resources

- **Repository**: https://github.com/trobz/local.py
- **Issues**: GitHub issues tracker
- **Documentation**: See docs/ directory
- **Bootstrap Script**: bootstrap.sh for quick setup
