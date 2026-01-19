# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

`trobz_local` (CLI: `tlc`) - Odoo dev environment automation tool.

```bash
uv sync && uv run pre-commit install  # Setup
make check                             # Lint + type check
make test                              # Run tests
uv run pytest tests/test_file.py -v    # Single test
make build                             # Build wheel
```

## Documentation

**Read `docs/` for details** - architecture, code standards, config examples:
- `docs/project-overview-pdr.md` - Features, requirements, config schema
- `docs/codebase-summary.md` - Module analysis
- `docs/code-standards.md` - Conventions, security practices
