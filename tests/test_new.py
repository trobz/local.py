"""Tests for tlc new command and odoo_dev_config module."""

import json
import os
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from trobz_local.main import app

runner = CliRunner()

SCHEMA_PATH = Path(__file__).parent.parent / "trobz_local" / "assets" / "odoo-dev.json"


# =============================================================================
# Helpers
# =============================================================================


def _read_config(target_dir: Path) -> dict:
    config_file = target_dir / ".odoo-dev.json"
    return json.loads(config_file.read_text())


def _create_local_checkout(code_dir: Path, version: str = "18.0") -> tuple[Path, Path]:
    checkout_root = code_dir / "odoo" / "odoo" / version
    addons_dir = checkout_root / "addons"
    odoo_addons_dir = checkout_root / "odoo" / "addons"
    addons_dir.mkdir(parents=True)
    odoo_addons_dir.mkdir(parents=True)
    return addons_dir, odoo_addons_dir


# =============================================================================
# 1. managed_layout — CLI returns managed layout with odoo_dir
# =============================================================================


def test_managed_layout(tmp_path):
    """Managed layout (e.g. trobz): sourcePaths == odoo_dir."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    code_dir = tmp_path / "code"
    code_dir.mkdir()

    odoo_addons = tmp_path / "project" / "odoo" / "addons"
    odoo_addons.mkdir(parents=True)
    odoo_odoo_addons = tmp_path / "project" / "odoo" / "odoo" / "addons"
    odoo_odoo_addons.mkdir(parents=True)

    cli_result = {
        "layout": "Trobz",
        "odoo_dir": [str(odoo_addons), str(odoo_odoo_addons)],
        "version": "18.0",
        "addons_path": "",
    }

    target_dir = cwd / ".claude"

    with (
        patch("trobz_local.odoo_dev_config._run_addons_path_cli", return_value=cli_result),
        patch("trobz_local.main._get_cwd", return_value=cwd),
        patch("trobz_local.main._get_global_config_dir", return_value=tmp_path / "global"),
    ):
        env = {**os.environ, "TLC_CODE_DIR": str(code_dir)}
        result = runner.invoke(app, ["--no-newcomer", "new"], env=env)
        assert result.exit_code == 0, result.output

    config = _read_config(target_dir)
    odoo_block = config["odoo_source"]
    assert odoo_block["layout"] == "trobz"
    assert odoo_block["sourcePaths"] != []
    assert str(odoo_addons) in odoo_block["sourcePaths"] or str(odoo_odoo_addons) in odoo_block["sourcePaths"]


# =============================================================================
# 2. local_layout — CLI returns fallback, local odoo checkout exists
# =============================================================================


def test_local_layout(tmp_path):
    """CLI fallback + local Odoo checkout at TLC_CODE_DIR/odoo/odoo/18.0 → layout=local."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    code_dir = tmp_path / "code"

    checkout_root = code_dir / "odoo" / "odoo" / "18.0"
    addons_dir = checkout_root / "addons"
    addons_dir.mkdir(parents=True)
    odoo_addons_dir = checkout_root / "odoo" / "addons"
    odoo_addons_dir.mkdir(parents=True)

    cli_result = {
        "layout": "fallback",
        "odoo_dir": [],
        "version": "18.0",
        "addons_path": "",
    }

    target_dir = cwd / ".claude"

    with (
        patch("trobz_local.odoo_dev_config._run_addons_path_cli", return_value=cli_result),
        patch("trobz_local.main._get_cwd", return_value=cwd),
        patch("trobz_local.main._get_global_config_dir", return_value=tmp_path / "global"),
    ):
        env = {**os.environ, "TLC_CODE_DIR": str(code_dir)}
        result = runner.invoke(app, ["--no-newcomer", "new"], env=env)
        assert result.exit_code == 0, result.output

    config = _read_config(target_dir)
    odoo_block = config["odoo_source"]
    assert odoo_block["layout"] == "local"
    assert str(addons_dir) in odoo_block["sourcePaths"]
    assert str(odoo_addons_dir) in odoo_block["sourcePaths"]
    for sp in odoo_block["sourcePaths"]:
        assert Path(sp).exists(), f"sourcePath does not exist: {sp}"


# =============================================================================
# 3. local_broken_tree — CLI returns fallback, local checkout exists but no addons dirs
# =============================================================================


def test_local_broken_tree(tmp_path):
    """CLI fallback + local checkout present but no addons dirs → unsupported."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    code_dir = tmp_path / "code"

    # Create checkout root but NO addons or odoo/addons inside
    checkout_root = code_dir / "odoo" / "odoo" / "18.0"
    checkout_root.mkdir(parents=True)

    cli_result = {
        "layout": "fallback",
        "odoo_dir": [],
        "version": "18.0",
        "addons_path": "",
    }

    target_dir = cwd / ".claude"

    with (
        patch("trobz_local.odoo_dev_config._run_addons_path_cli", return_value=cli_result),
        patch("trobz_local.main._get_cwd", return_value=cwd),
        patch("trobz_local.main._get_global_config_dir", return_value=tmp_path / "global"),
    ):
        env = {**os.environ, "TLC_CODE_DIR": str(code_dir)}
        result = runner.invoke(app, ["--no-newcomer", "new"], env=env)
        assert result.exit_code == 1, result.output

    assert not (target_dir / ".odoo-dev.json").exists()
    assert "Could not resolve an Odoo source layout" in result.output


# =============================================================================
# 4. unsupported_with_version — CLI returns fallback, no local checkout
# =============================================================================


def test_unsupported_with_version(tmp_path):
    """CLI fallback, no local source, version resolvable → unsupported."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    code_dir = tmp_path / "code"
    code_dir.mkdir(parents=True)

    cli_result = {
        "layout": "fallback",
        "odoo_dir": [],
        "version": "18.0",
        "addons_path": "",
    }

    target_dir = cwd / ".claude"

    with (
        patch("trobz_local.odoo_dev_config._run_addons_path_cli", return_value=cli_result),
        patch("trobz_local.main._get_cwd", return_value=cwd),
        patch("trobz_local.main._get_global_config_dir", return_value=tmp_path / "global"),
    ):
        env = {**os.environ, "TLC_CODE_DIR": str(code_dir)}
        result = runner.invoke(app, ["--no-newcomer", "new"], env=env)
        assert result.exit_code == 1, result.output

    assert not (target_dir / ".odoo-dev.json").exists()
    assert "Could not resolve an Odoo source layout" in result.output


# =============================================================================
# 5. unsupported_unresolvable — CLI returns null layout and null version
# =============================================================================


def test_unsupported_unresolvable(tmp_path):
    """CLI null layout + null version, no local source → unsupported."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    code_dir = tmp_path / "code"
    code_dir.mkdir(parents=True)

    cli_result = {
        "layout": None,
        "odoo_dir": [],
        "version": None,
        "addons_path": "",
    }

    target_dir = cwd / ".claude"

    with (
        patch("trobz_local.odoo_dev_config._run_addons_path_cli", return_value=cli_result),
        patch("trobz_local.main._get_cwd", return_value=cwd),
        patch("trobz_local.main._get_global_config_dir", return_value=tmp_path / "global"),
    ):
        env = {**os.environ, "TLC_CODE_DIR": str(code_dir)}
        result = runner.invoke(app, ["--no-newcomer", "new"], env=env)
        assert result.exit_code == 1, result.output

    assert not (target_dir / ".odoo-dev.json").exists()
    assert "Could not resolve an Odoo source layout" in result.output


# =============================================================================
# 6. manifest_less_no_source — CLI absent/broken and no checkout → unsupported
# =============================================================================


def test_manifest_less_no_source(tmp_path):
    """CLI absent/broken (_run_addons_path_cli returns None) and no checkout → unsupported."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    code_dir = tmp_path / "code"
    code_dir.mkdir(parents=True)

    target_dir = cwd / ".claude"

    with (
        patch("trobz_local.odoo_dev_config._run_addons_path_cli", return_value=None),
        patch("trobz_local.main._get_cwd", return_value=cwd),
        patch("trobz_local.main._get_global_config_dir", return_value=tmp_path / "global"),
    ):
        env = {**os.environ, "TLC_CODE_DIR": str(code_dir)}
        result = runner.invoke(app, ["--no-newcomer", "new"], env=env)

    assert result.exit_code == 1, result.output
    assert not (target_dir / ".odoo-dev.json").exists()
    assert "Could not resolve an Odoo source layout" in result.output


# =============================================================================
# 7. cli_version_null_git_branch_fallback — CLI version null, branch has version prefix
# =============================================================================


def test_cli_version_null_git_branch_fallback(tmp_path):
    """CLI version null → git-branch fallback yields version from branch name."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    code_dir = tmp_path / "code"
    code_dir.mkdir(parents=True)
    _create_local_checkout(code_dir)

    cli_result = {
        "layout": None,
        "odoo_dir": [],
        "version": None,
        "addons_path": "",
    }

    target_dir = cwd / ".claude"

    with (
        patch("trobz_local.odoo_dev_config._run_addons_path_cli", return_value=cli_result),
        patch("trobz_local.odoo_dev_config._git_branch_version", return_value="18.0"),
        patch("trobz_local.main._get_cwd", return_value=cwd),
        patch("trobz_local.main._get_global_config_dir", return_value=tmp_path / "global"),
    ):
        env = {**os.environ, "TLC_CODE_DIR": str(code_dir)}
        result = runner.invoke(app, ["--no-newcomer", "new"], env=env)
        assert result.exit_code == 0, result.output

    config = _read_config(target_dir)
    odoo_block = config["odoo_source"]
    assert odoo_block["layout"] == "local"
    assert odoo_block.get("version") == "18.0"


# =============================================================================
# 8. global_flag — -g writes to ~/.claude/ not CWD
# =============================================================================


def test_global_flag(tmp_path):
    """--global flag writes odoo-dev.json to the global dir, not CWD/.claude/."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    code_dir = tmp_path / "code"
    code_dir.mkdir(parents=True)
    _create_local_checkout(code_dir)

    fake_home_claude = tmp_path / "home" / ".claude"
    fake_home_claude.mkdir(parents=True)

    cli_result = {
        "layout": None,
        "odoo_dir": [],
        "version": "18.0",
        "addons_path": "",
    }

    with (
        patch("trobz_local.odoo_dev_config._run_addons_path_cli", return_value=cli_result),
        patch("trobz_local.main._get_cwd", return_value=cwd),
        patch("trobz_local.main._get_global_config_dir", return_value=fake_home_claude),
    ):
        env = {**os.environ, "TLC_CODE_DIR": str(code_dir)}
        result = runner.invoke(app, ["--no-newcomer", "new", "-g"], env=env)
        assert result.exit_code == 0, result.output

    global_config = fake_home_claude / ".odoo-dev.json"
    assert global_config.exists(), "Config not written to global dir"
    local_config = cwd / ".claude" / ".odoo-dev.json"
    assert not local_config.exists(), "Config must NOT be written to CWD when --global used"


# =============================================================================
# 9. overwrite_force — --force overwrites, creates .bak, sibling keys untouched
# =============================================================================


def test_overwrite_force(tmp_path):
    """--force overwrites existing odoo-dev.json, creates .bak, preserves other root keys."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    code_dir = tmp_path / "code"
    code_dir.mkdir(parents=True)
    _create_local_checkout(code_dir)

    target_dir = cwd / ".claude"
    target_dir.mkdir(parents=True)

    existing = {
        "odoo_source": {"layout": "local", "sourcePaths": ["/old/addons"], "version": "17.0"},
        "extra_key": "should_remain",
    }
    config_file = target_dir / ".odoo-dev.json"
    config_file.write_text(json.dumps(existing))

    cli_result = {
        "layout": None,
        "odoo_dir": [],
        "version": "18.0",
        "addons_path": "",
    }

    with (
        patch("trobz_local.odoo_dev_config._run_addons_path_cli", return_value=cli_result),
        patch("trobz_local.main._get_cwd", return_value=cwd),
        patch("trobz_local.main._get_global_config_dir", return_value=tmp_path / "global"),
    ):
        env = {**os.environ, "TLC_CODE_DIR": str(code_dir)}
        result = runner.invoke(app, ["--no-newcomer", "new", "--force"], env=env)
        assert result.exit_code == 0, result.output

    bak_file = target_dir / ".odoo-dev.json.bak"
    assert bak_file.exists(), ".bak file not created"

    updated = json.loads(config_file.read_text())
    assert updated["odoo_source"]["version"] == "18.0"
    assert updated.get("extra_key") == "should_remain"


# =============================================================================
# 10. schema_valid — written file validates against JSON Schema
# =============================================================================


def test_schema_valid(tmp_path):
    """Written odoo-dev.json validates against schema/odoo-dev.json."""
    import jsonschema

    cwd = tmp_path / "project"
    cwd.mkdir()
    code_dir = tmp_path / "code"
    code_dir.mkdir(parents=True)
    _create_local_checkout(code_dir)

    target_dir = cwd / ".claude"

    cli_result = {
        "layout": None,
        "odoo_dir": [],
        "version": "18.0",
        "addons_path": "",
    }

    with (
        patch("trobz_local.odoo_dev_config._run_addons_path_cli", return_value=cli_result),
        patch("trobz_local.main._get_cwd", return_value=cwd),
        patch("trobz_local.main._get_global_config_dir", return_value=tmp_path / "global"),
    ):
        env = {**os.environ, "TLC_CODE_DIR": str(code_dir)}
        result = runner.invoke(app, ["--no-newcomer", "new"], env=env)
        assert result.exit_code == 0, result.output

    schema = json.loads(SCHEMA_PATH.read_text())
    config = _read_config(target_dir)
    jsonschema.validate(config, schema)


# =============================================================================
# 11. local_layout_with_enterprise — enterprise sibling present → enterprisePaths set
# =============================================================================


def test_local_layout_with_enterprise(tmp_path):
    """Local layout + enterprise/<version> sibling exists → enterprisePaths included."""
    import jsonschema

    cwd = tmp_path / "project"
    cwd.mkdir()
    code_dir = tmp_path / "code"

    checkout_root = code_dir / "odoo" / "odoo" / "18.0"
    addons_dir = checkout_root / "addons"
    addons_dir.mkdir(parents=True)

    enterprise_root = code_dir / "odoo" / "enterprise" / "18.0"
    enterprise_module = enterprise_root / "some_module" / "__manifest__.py"
    enterprise_module.parent.mkdir(parents=True)
    enterprise_module.write_text("{}")

    cli_result = {
        "layout": "fallback",
        "odoo_dir": [],
        "version": "18.0",
        "addons_path": "",
    }

    target_dir = cwd / ".claude"

    with (
        patch("trobz_local.odoo_dev_config._run_addons_path_cli", return_value=cli_result),
        patch("trobz_local.main._get_cwd", return_value=cwd),
        patch("trobz_local.main._get_global_config_dir", return_value=tmp_path / "global"),
    ):
        env = {**os.environ, "TLC_CODE_DIR": str(code_dir)}
        result = runner.invoke(app, ["--no-newcomer", "new"], env=env)
        assert result.exit_code == 0, result.output

    config = _read_config(target_dir)
    odoo_block = config["odoo_source"]
    assert odoo_block["layout"] == "local"
    assert odoo_block["enterprisePaths"] == [str(enterprise_root)]

    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(config, schema)


# =============================================================================
# 12. local_layout_without_enterprise — no enterprise sibling → no enterprisePaths key
# =============================================================================


def test_local_layout_without_enterprise(tmp_path):
    """Local layout, no enterprise/<version> sibling → enterprisePaths key absent."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    code_dir = tmp_path / "code"

    checkout_root = code_dir / "odoo" / "odoo" / "18.0"
    addons_dir = checkout_root / "addons"
    addons_dir.mkdir(parents=True)

    cli_result = {
        "layout": "fallback",
        "odoo_dir": [],
        "version": "18.0",
        "addons_path": "",
    }

    target_dir = cwd / ".claude"

    with (
        patch("trobz_local.odoo_dev_config._run_addons_path_cli", return_value=cli_result),
        patch("trobz_local.main._get_cwd", return_value=cwd),
        patch("trobz_local.main._get_global_config_dir", return_value=tmp_path / "global"),
    ):
        env = {**os.environ, "TLC_CODE_DIR": str(code_dir)}
        result = runner.invoke(app, ["--no-newcomer", "new"], env=env)
        assert result.exit_code == 0, result.output

    config = _read_config(target_dir)
    odoo_block = config["odoo_source"]
    assert odoo_block["layout"] == "local"
    assert "enterprisePaths" not in odoo_block


# =============================================================================
# 13. managed_layout_no_enterprise_omits_key — no enterprise sibling → no key
# =============================================================================


def test_managed_layout_no_enterprise_omits_key(tmp_path):
    """Managed layout (trobz) without enterprise sibling: enterprisePaths key absent."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    code_dir = tmp_path / "code"
    code_dir.mkdir()

    odoo_addons = tmp_path / "project" / "odoo" / "addons"
    odoo_addons.mkdir(parents=True)

    cli_result = {
        "layout": "Trobz",
        "odoo_dir": [str(odoo_addons)],
        "version": "18.0",
        "addons_path": "",
    }

    target_dir = cwd / ".claude"

    with (
        patch("trobz_local.odoo_dev_config._run_addons_path_cli", return_value=cli_result),
        patch("trobz_local.main._get_cwd", return_value=cwd),
        patch("trobz_local.main._get_global_config_dir", return_value=tmp_path / "global"),
    ):
        env = {**os.environ, "TLC_CODE_DIR": str(code_dir)}
        result = runner.invoke(app, ["--no-newcomer", "new"], env=env)
        assert result.exit_code == 0, result.output

    config = _read_config(target_dir)
    odoo_block = config["odoo_source"]
    assert odoo_block["layout"] == "trobz"
    assert "enterprisePaths" not in odoo_block


# =============================================================================
# 14. managed_layout_empty_source_paths_falls_through — all odoo_dir missing → fallthrough
# =============================================================================


def test_managed_layout_empty_source_paths_falls_through(tmp_path):
    """Managed layout with all-missing odoo_dir entries falls through to local checkout."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    code_dir = tmp_path / "code"
    code_dir.mkdir()
    _create_local_checkout(code_dir)

    cli_result = {
        "layout": "Trobz",
        "odoo_dir": ["/does/not/exist/addons"],
        "version": "18.0",
        "addons_path": "",
    }

    target_dir = cwd / ".claude"

    with (
        patch("trobz_local.odoo_dev_config._run_addons_path_cli", return_value=cli_result),
        patch("trobz_local.main._get_cwd", return_value=cwd),
        patch("trobz_local.main._get_global_config_dir", return_value=tmp_path / "global"),
    ):
        env = {**os.environ, "TLC_CODE_DIR": str(code_dir)}
        result = runner.invoke(app, ["--no-newcomer", "new"], env=env)
        assert result.exit_code == 0, result.output

    config = _read_config(target_dir)
    odoo_block = config["odoo_source"]
    # Must NOT emit a managed block with empty sourcePaths
    assert odoo_block["layout"] != "trobz" or odoo_block.get("sourcePaths") != []
    assert odoo_block["layout"] == "local"


# =============================================================================
# 15. odoosh_layout_with_enterprise_symlink — cwd/enterprise symlink → enterprisePaths set
# =============================================================================


def test_odoosh_layout_with_enterprise_symlink(tmp_path):
    """odoo.sh layout with cwd/enterprise symlink: enterprisePaths resolves to real target."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    code_dir = tmp_path / "code"
    code_dir.mkdir()

    odoo_addons = cwd / "odoo" / "addons"
    odoo_addons.mkdir(parents=True)

    # Create a real enterprise dir and symlink it at cwd/enterprise
    real_enterprise = tmp_path / "real-enterprise"
    real_enterprise.mkdir()
    enterprise_link = cwd / "enterprise"
    enterprise_link.symlink_to(real_enterprise)

    cli_result = {
        "layout": "odoo.sh",
        "odoo_dir": [str(odoo_addons)],
        "version": "18.0",
        "addons_path": "",
    }

    target_dir = cwd / ".claude"

    with (
        patch("trobz_local.odoo_dev_config._run_addons_path_cli", return_value=cli_result),
        patch("trobz_local.main._get_cwd", return_value=cwd),
        patch("trobz_local.main._get_global_config_dir", return_value=tmp_path / "global"),
    ):
        env = {**os.environ, "TLC_CODE_DIR": str(code_dir)}
        result = runner.invoke(app, ["--no-newcomer", "new"], env=env)
        assert result.exit_code == 0, result.output

    config = _read_config(target_dir)
    odoo_block = config["odoo_source"]
    assert odoo_block["layout"] == "odoosh"
    assert "enterprisePaths" in odoo_block
    assert odoo_block["enterprisePaths"] == [str(real_enterprise.resolve())]


# =============================================================================
# 16. odoosh_layout_without_enterprise — no cwd/enterprise dir → no key
# =============================================================================


def test_odoosh_layout_without_enterprise(tmp_path):
    """odoo.sh layout without cwd/enterprise dir: enterprisePaths key absent."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    code_dir = tmp_path / "code"
    code_dir.mkdir()

    odoo_addons = cwd / "odoo" / "addons"
    odoo_addons.mkdir(parents=True)

    cli_result = {
        "layout": "odoo.sh",
        "odoo_dir": [str(odoo_addons)],
        "version": "18.0",
        "addons_path": "",
    }

    target_dir = cwd / ".claude"

    with (
        patch("trobz_local.odoo_dev_config._run_addons_path_cli", return_value=cli_result),
        patch("trobz_local.main._get_cwd", return_value=cwd),
        patch("trobz_local.main._get_global_config_dir", return_value=tmp_path / "global"),
    ):
        env = {**os.environ, "TLC_CODE_DIR": str(code_dir)}
        result = runner.invoke(app, ["--no-newcomer", "new"], env=env)
        assert result.exit_code == 0, result.output

    config = _read_config(target_dir)
    odoo_block = config["odoo_source"]
    assert odoo_block["layout"] == "odoosh"
    assert "enterprisePaths" not in odoo_block


# =============================================================================
# 17. trobz_layout_with_enterprise_sibling — code_dir/odoo/enterprise/<version> present
# =============================================================================


def test_trobz_layout_with_enterprise_sibling(tmp_path):
    """Managed trobz layout with enterprise sibling at code_dir/odoo/enterprise/<version>."""
    cwd = tmp_path / "project"
    cwd.mkdir()
    code_dir = tmp_path / "code"
    code_dir.mkdir()

    odoo_addons = cwd / "odoo" / "addons"
    odoo_addons.mkdir(parents=True)

    enterprise_dir = code_dir / "odoo" / "enterprise" / "18.0"
    enterprise_dir.mkdir(parents=True)

    cli_result = {
        "layout": "Trobz",
        "odoo_dir": [str(odoo_addons)],
        "version": "18.0",
        "addons_path": "",
    }

    target_dir = cwd / ".claude"

    with (
        patch("trobz_local.odoo_dev_config._run_addons_path_cli", return_value=cli_result),
        patch("trobz_local.main._get_cwd", return_value=cwd),
        patch("trobz_local.main._get_global_config_dir", return_value=tmp_path / "global"),
    ):
        env = {**os.environ, "TLC_CODE_DIR": str(code_dir)}
        result = runner.invoke(app, ["--no-newcomer", "new"], env=env)
        assert result.exit_code == 0, result.output

    config = _read_config(target_dir)
    odoo_block = config["odoo_source"]
    assert odoo_block["layout"] == "trobz"
    assert "enterprisePaths" in odoo_block
    assert odoo_block["enterprisePaths"] == [str(enterprise_dir.resolve())]
