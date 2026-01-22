# Code Standards & Structure

Development guidelines, architectural patterns, and best practices for `trobz_local`.

## Project Architecture

Four-layer modular design with clear separation of concerns:

| Layer | Module(s) | Responsibility |
|---|---|---|
| **CLI Layer** | `main.py` | Command routing, user interaction, newcomer mode |
| **Implementation** | `installers.py` | Four installation strategies (script, system, npm, uv) |
| **Utility Layer** | `utils.py` | Config validation, platform detection, helpers |
| **Infrastructure** | `concurrency.py`, `exceptions.py` | Parallel execution, custom exceptions |

---

## Code Style Guidelines

### Python Conventions
- **Standard**: PEP 8 compliance
- **Formatter**: ruff (fast, deterministic)
- **Line Length**: Max 120 characters (ruff.toml config)
- **Import Order**: stdlib → third-party → local (ruff-managed)
- **Active Rules**: YTT, S (security), B, A, C4, T10, SIM, I, C90, E, W, F, PGH, UP, RUF, TRY

### Type Safety (Mandatory)
- All function signatures must have type hints
- Complex variables must be annotated
- Static analysis via mypy (ty wrapper)
- Pydantic for external data validation (config.toml)

### Naming Rules

| Element | Pattern | Example |
|---|---|---|
| Modules | snake_case | `installers.py` |
| Classes | PascalCase | `ConfigModel` |
| Functions | snake_case | `pull_repos` |
| Constants | SCREAMING_SNAKE_CASE | `ARCH_PACKAGES` |
| Private | _snake_case | `_run_installers` |

---

## Architectural Patterns

### 1. Declarative Configuration
System state defined in TOML. Tool reconciles local environment with definition. Pydantic validates before any side effects.

### 2. Strategy Pattern
`installers.py`: Multiple strategies per tool source (script, system packages, npm, uv) with OS-aware selection.

### 3. Command Pattern
`main.py`: Each CLI command is discrete but shares context (newcomer mode, dry-run). Easy to add new commands.

### 4. Observer Pattern
`GitProgress` and `run_tasks()`: Real-time progress callbacks to Rich UI. Decoupled from execution logic.

### 5. Fail-Fast Validation
Config validated at startup. Early detection prevents side effects on invalid input.

---

## Security Requirements

### Subprocess Safety
- **Never use shell=True** - Always pass arguments as list
- **Full paths only** - Use shutil.which() instead of relying on PATH
- **No user input in commands** - Build commands from validated config only

### Download Security
- **HTTPS enforcement** - Pydantic validator rejects non-HTTPS URLs
- **Trusted sources only** - Script URLs must be whitelisted or reviewed

### Input Validation
- **Regex patterns** - All config fields validated with specific patterns:
  - Versions: `^\d+\.\d+$`
  - UV tools: `^[a-zA-Z0-9][a-zA-Z0-9._\-\[\]@=<>!,]*$`
  - Repo names: `^[a-zA-Z0-9._-]+$`
- **Pydantic models** - No ad-hoc parsing of config
- **Ruff S* rules** - Security linting enabled in make check

### Credential Handling
- No credentials stored in code
- No sensitive data logged
- Environment variables used for user-specific paths only

---

## Error Handling Patterns

### Custom Exceptions
Use specialized exceptions from `exceptions.py` with context:
```python
raise DownloadError(url=script_url, reason=str(e))
raise ExecutableNotFoundError(executable="wget")
```

### Fail Paths
1. **Config errors**: Print message + example, exit 1
2. **Task failures**: Catch exception, record in TaskResult, continue
3. **Validation errors**: Pydantic prints field-level details, exit 1

### Cleanup
- Use context managers for temporary files
- Temporary directories auto-deleted on function exit
- No partial state on failure

---

## Testing Requirements

### Framework
- **Tool**: pytest
- **Mocking**: unittest.mock for filesystem, network, subprocesses
- **Coverage**: All new features must include tests
- **No real I/O**: Tests must not actually download, install, or git-clone

### Test Organization
- Test file naming: `test_{module}.py`
- Test function naming: `test_{function}_case_description`
- Fixtures for common setup
- Parametrized tests for multiple scenarios

### Running Tests
```bash
make test              # Full suite
pytest -xvs file.py  # Single file with verbose output
pytest --cov         # Coverage report
```

---

## Development Workflow

### Setup
```bash
uv sync              # Install dependencies
uv run pre-commit install  # Setup git hooks
make check           # Verify setup (lint + type check)
```

### Code Quality Checklist
- [ ] Code follows naming conventions and style guidelines
- [ ] Type hints on all function signatures
- [ ] Tests written and passing (make test)
- [ ] Linting passes (make check)
- [ ] No security issues (ruff S rules)
- [ ] Error handling implemented
- [ ] Documentation updated

### Before Committing
```bash
make check  # Linters + type checkers
make test   # Full test suite
```

### Commit Message Format
Follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat: description` - New feature
- `fix: description` - Bug fix
- `docs: description` - Documentation
- `refactor: description` - Code restructuring
- `test: description` - Test additions
- `chore: description` - Maintenance

---

## File Structure

**Max file size**: 500 LOC (split if larger)
- `main.py`: CLI commands and orchestration (452 LOC)
- `installers.py`: Installation strategies (282 LOC)
- `utils.py`: Config, platform detection, helpers (264 LOC)
- `concurrency.py`: Task runner with progress (60 LOC)
- `exceptions.py`: Custom exception classes (38 LOC)
- `tests/`: pytest unit tests for all modules

**Imports in each module**:
- No circular imports
- Public functions documented
- Private functions start with underscore

---

## Documentation Standards

### Docstrings (Google Style)
```python
def function(param: Type) -> ReturnType:
    """Brief one-line description.

    Longer description if needed.

    Args:
        param: Description

    Returns:
        Description of return value

    Raises:
        CustomError: When this happens
    """
```

### Code Comments
- Explain "why", not "what"
- Comment complex logic only
- Keep comments synchronized with code

### Inline Documentation
- Update docs/ files when changing features
- Keep code examples in docs/ current
- Reference specific line numbers when helpful
