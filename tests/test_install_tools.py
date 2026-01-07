"""Tests for install_tools command with new multi-package support."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from trobz_local.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_typer_confirm():
    with patch("typer.confirm", return_value=True) as mock_tc:
        yield mock_tc


# =============================================================================
# UV Tools Tests
# =============================================================================


@patch("trobz_local.installers.shutil.which")
@patch("trobz_local.main.get_config")
@patch("trobz_local.installers.subprocess.run")
def test_install_uv_tools(mock_subprocess, mock_get_config, mock_which):
    mock_which.return_value = "/usr/bin/uv"
    mock_get_config.return_value = {
        "tools": {
            "uv": ["invoke", "git-aggregator"],
            "npm": [],
            "script": [],
            "system_packages": [],
        }
    }

    result = runner.invoke(app, ["--no-newcomer", "install-tools"])

    assert result.exit_code == 0
    # Each uv tool is installed in parallel, so we expect 2 calls
    assert mock_subprocess.call_count == 2


@patch("trobz_local.installers.shutil.which")
@patch("trobz_local.main.get_config")
@patch("trobz_local.installers.subprocess.run")
def test_install_tools_empty_config(mock_subprocess, mock_get_config, mock_which):
    mock_which.return_value = "/usr/bin/uv"
    mock_get_config.return_value = {"tools": {}}  # Empty tools config

    result = runner.invoke(app, ["--no-newcomer", "install-tools"])

    assert result.exit_code == 0
    mock_subprocess.assert_not_called()
    assert "No tools found in config" in result.stdout


@patch("trobz_local.installers.shutil.which")
@patch("trobz_local.main.get_config")
@patch("trobz_local.installers.subprocess.run")
def test_install_tools_uv_missing(mock_subprocess, mock_get_config, mock_which):
    mock_which.return_value = None  # uv not found
    mock_get_config.return_value = {
        "tools": {
            "uv": ["invoke"],
            "npm": [],
            "script": [],
            "system_packages": [],
        }
    }

    result = runner.invoke(app, ["--no-newcomer", "install-tools"])

    assert result.exit_code == 1
    assert "uv is not installed" in result.stdout


# =============================================================================
# Dry Run Tests
# =============================================================================


@patch("trobz_local.installers.shutil.which")
@patch("trobz_local.main.get_config")
def test_install_tools_dry_run(mock_get_config, mock_which):
    mock_which.return_value = "/usr/bin/uv"
    mock_get_config.return_value = {
        "tools": {
            "uv": ["ruff", "pre-commit"],
            "npm": ["prettier"],
            "script": [{"url": "https://example.com/install.sh"}],
            "system_packages": ["git"],
        }
    }

    result = runner.invoke(app, ["--no-newcomer", "install-tools", "--dry-run"])

    assert result.exit_code == 0
    # Verify dry-run output contains all categories
    assert "Scripts - would be downloaded" in result.stdout
    assert "System packages - would be installed" in result.stdout
    assert "NPM packages - would be installed" in result.stdout
    assert "UV tools - would be installed" in result.stdout


# =============================================================================
# NPM Packages Tests
# =============================================================================


@patch("trobz_local.installers.shutil.which")
@patch("trobz_local.main.get_config")
@patch("trobz_local.installers.subprocess.run")
def test_install_npm_packages_pnpm_missing(mock_subprocess, mock_get_config, mock_which):
    # pnpm not found
    mock_which.side_effect = lambda cmd: None if cmd == "pnpm" else "/usr/bin/uv"
    mock_get_config.return_value = {
        "tools": {
            "uv": [],
            "npm": ["prettier"],
            "script": [],
            "system_packages": [],
        }
    }

    result = runner.invoke(app, ["--no-newcomer", "install-tools"])

    assert result.exit_code == 1
    assert "pnpm is not installed" in result.stdout


@patch("trobz_local.installers.shutil.which")
@patch("trobz_local.main.get_config")
@patch("trobz_local.installers.subprocess.run")
def test_install_npm_packages_success(mock_subprocess, mock_get_config, mock_which):
    mock_which.return_value = "/usr/bin/pnpm"
    mock_get_config.return_value = {
        "tools": {
            "uv": [],
            "npm": ["prettier", "eslint"],
            "script": [],
            "system_packages": [],
        }
    }

    result = runner.invoke(app, ["--no-newcomer", "install-tools"])

    assert result.exit_code == 0
    # Each npm package is installed in parallel
    assert mock_subprocess.call_count == 2


# =============================================================================
# System Packages Tests
# =============================================================================


@patch("trobz_local.installers.get_os_info")
@patch("trobz_local.installers.shutil.which")
@patch("trobz_local.main.get_config")
@patch("trobz_local.installers.subprocess.run")
def test_install_system_packages_arch(mock_subprocess, mock_get_config, mock_which, mock_os_info):
    mock_os_info.return_value = {"system": "Linux", "distro": "arch"}
    mock_which.return_value = "/usr/bin/pacman"
    mock_get_config.return_value = {
        "tools": {
            "uv": [],
            "npm": [],
            "script": [],
            "system_packages": ["pnpm"],
        }
    }

    result = runner.invoke(app, ["--no-newcomer", "install-tools"])

    assert result.exit_code == 0
    # System packages are installed as a single batch
    mock_subprocess.assert_called_once()
    call_args = mock_subprocess.call_args[0][0]
    assert "pacman" in call_args
    assert "pnpm" in call_args


@patch("trobz_local.installers.get_os_info")
@patch("trobz_local.installers.shutil.which")
@patch("trobz_local.main.get_config")
def test_install_system_packages_unsupported_os(mock_get_config, mock_which, mock_os_info):
    mock_os_info.return_value = {"system": "Windows", "distro": "unknown"}
    mock_which.return_value = None
    mock_get_config.return_value = {
        "tools": {
            "uv": [],
            "npm": [],
            "script": [],
            "system_packages": ["git"],
        }
    }

    result = runner.invoke(app, ["--no-newcomer", "install-tools"])

    # Should show error for unsupported OS
    assert "Unsupported operating system" in result.stdout


# =============================================================================
# Script Tests
# =============================================================================


@patch("trobz_local.installers.shutil.which")
@patch("trobz_local.main.get_config")
@patch("trobz_local.installers.subprocess.run")
def test_install_script_success(mock_subprocess, mock_get_config, mock_which):
    """Script downloads and executes successfully."""

    def which_side_effect(cmd):
        if cmd == "curl":
            return "/usr/bin/curl"
        if cmd == "sh":
            return "/bin/sh"
        return None

    mock_which.side_effect = which_side_effect

    content = b"#!/bin/sh\necho 'test'"

    mock_get_config.return_value = {
        "tools": {
            "uv": [],
            "npm": [],
            "script": [{"url": "https://example.com/test.sh"}],
            "system_packages": [],
        }
    }

    def subprocess_side_effect(cmd, **kwargs):
        if "-o" in cmd:
            idx = cmd.index("-o")
            output_path = Path(cmd[idx + 1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(content)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    mock_subprocess.side_effect = subprocess_side_effect

    result = runner.invoke(app, ["--no-newcomer", "install-tools"])

    assert result.exit_code == 0
    assert "✓ https://example.com/test.sh executed." in result.stdout
