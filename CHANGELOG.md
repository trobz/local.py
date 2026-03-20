# CHANGELOG

<!-- version list -->

## v0.8.0 (2026-03-20)

### Bug Fixes

- Honor --yes flag in generate-config to skip overwrite prompt
  ([`f48c434`](https://github.com/trobz/local.py/commit/f48c434ca5c3084106d7cce5b1f3debd78b4b93c))

- Prepend remote content before local assets to fix TOML table scoping
  ([`eef0fdf`](https://github.com/trobz/local.py/commit/eef0fdfc0e318dd92317c133c9bba093894d79d5))

- Use importlib.resources for asset files so they work when installed as a package
  ([`93c34e5`](https://github.com/trobz/local.py/commit/93c34e54e5717ff5af94f27944fb91a1ff937a68))

### Features

- Add generate-config command with odoo-minimal and oca-contributor profiles
  ([`4674719`](https://github.com/trobz/local.py/commit/46747199c9352e17c4639f74ff80296e5ddb8731))

### Refactoring

- Move generate-config before init in command registration order
  ([`a1a3320`](https://github.com/trobz/local.py/commit/a1a332093840c96fa2be7cb4f1c8abe3fdade2ca))


## v0.7.1 (2026-03-16)

### Bug Fixes

- Add help description to init command
  ([`2986e13`](https://github.com/trobz/local.py/commit/2986e131f11e616b8a7cd0fd69762af466bd0986))

- **doctor**: Add help description to doctor command
  ([`244e0b5`](https://github.com/trobz/local.py/commit/244e0b54deffd28ed53496263d16345dfd472399))


## v0.7.0 (2026-03-03)

### Bug Fixes

- Hide completed progress tasks to avoid terminal overflow
  ([`ecad576`](https://github.com/trobz/local.py/commit/ecad576033efe3aacbfc26eaca1a1268ab396bd6))

### Features

- Support generic GitHub orgs and per-repo branch override in config
  ([`f256125`](https://github.com/trobz/local.py/commit/f25612550c503a0297aa226f4210c77829792cd2))

- **doctor**: Add health check command for environment diagnostics
  ([`dba5a1d`](https://github.com/trobz/local.py/commit/dba5a1d81fd33a492b8638fd6de193776b36824d))

### Refactoring

- Generalize _get_tasks to handle any GitHub org
  ([`b47b2fa`](https://github.com/trobz/local.py/commit/b47b2fae4d0b385704d0a1b0b47aca94e8cb5e42))


## v0.6.0 (2026-02-26)

### Features

- Add create_launcher configuration option for venv setup
  ([`e64e05b`](https://github.com/trobz/local.py/commit/e64e05b5a849ebf3cd33b4c4a694f27fc90bd2d5))


## v0.5.0 (2026-02-25)

### Bug Fixes

- Always install default system packages in install-tools
  ([`04bb2a4`](https://github.com/trobz/local.py/commit/04bb2a4ea2a8eb3c8d0d09bc5c7e46137d38b675))

- Prevent bootstrap.sh from running as root
  ([`491f7d2`](https://github.com/trobz/local.py/commit/491f7d2bd3b5a47fb63c1b7f24fec27b2573f62f))

### Documentation

- Remove uv script entry from project-overview-pdr example config
  ([`1af9e5f`](https://github.com/trobz/local.py/commit/1af9e5f0d493824f7cdb83adf4a85c0dcceb8d83))

- Remove uv script entry from README example config
  ([`2f4648c`](https://github.com/trobz/local.py/commit/2f4648c103184f702e9c8b5d8bad67f41b887b5a))

### Features

- Add -y/--yes flag for non-interactive mode
  ([`c9d95ef`](https://github.com/trobz/local.py/commit/c9d95efbc888e59e9367216813311b1c6e302d65))

### Refactoring

- Extract config example to assets/odoo_dev.toml
  ([`86dbd18`](https://github.com/trobz/local.py/commit/86dbd18aba985a4200037d51ba4205d57fe85690))


## v0.4.0 (2026-02-23)

### Bug Fixes

- Update command running odoo-venv
  ([`593ea78`](https://github.com/trobz/local.py/commit/593ea78b97bf0be4ca0c62e6227aea4735d6291f))

### Features

- **db**: Add ensure-db-user CLI command for PostgreSQL user management
  ([`661a40f`](https://github.com/trobz/local.py/commit/661a40f8a892c4c2e94f5a13642f5fddb3400cdb))

### Refactoring

- **init**: Use hardcoded defaults with configurable extra dirs
  ([`949567f`](https://github.com/trobz/local.py/commit/949567f064035184452a136bfbb00cde5ce19dc7))

- **install**: Improve bootstrap and installer architecture
  ([`a408d99`](https://github.com/trobz/local.py/commit/a408d99c483dd3d1aef7348d31f6316dd12fa737))


## v0.3.0 (2026-01-28)

### Documentation

- Update codebase metrics and version validation regex
  ([`d333d03`](https://github.com/trobz/local.py/commit/d333d0300efc7569eebebc1daf0f9f1efb8c638f))

### Features

- Add master as valid branch to pull
  ([`b1d69ac`](https://github.com/trobz/local.py/commit/b1d69acdc98df7c69aa6e73c72bca29336002b59))


## v0.2.0 (2026-01-22)

### Documentation

- Update documentation for configurable code directory
  ([`ea92f93`](https://github.com/trobz/local.py/commit/ea92f939055ce1d4dd57ee4c0632c92824d15e89))

- **code-standards**: Add test coverage and LOC guidelines
  ([`c42eab8`](https://github.com/trobz/local.py/commit/c42eab8a0036f8e00c777b73ab0237a3ad18682e))

- **codebase-summary**: Update Python version, add toml info, note tests
  ([`f615db5`](https://github.com/trobz/local.py/commit/f615db5d1db105af8cd794324e3fa674ecc5ff06))

- **system-architecture**: Update decorator signature and max_workers config
  ([`74e701a`](https://github.com/trobz/local.py/commit/74e701a53cf1b061a377eaeeb1e773b6ca800eba))

### Features

- Add get_code_root() helper for configurable code directory
  ([`d499d2d`](https://github.com/trobz/local.py/commit/d499d2d5fd216cc3a71a54f4a33b821c37da1756))

- **config**: Update main commands to use configurable code directory
  ([`e3c7c05`](https://github.com/trobz/local.py/commit/e3c7c05ea6b6c64f411717384a3e01395bf87b79))


## v0.1.0 (2026-01-19)

### Features

- Extend install-tools
  ([`94f4c63`](https://github.com/trobz/local.py/commit/94f4c636af86b48fd17df047dab3d2c08d66c8b0))


## v0.0.0 (2026-01-06)

- Initial Release
