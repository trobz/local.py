import subprocess
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from trobz_local.doctor import (
    CheckResult,
    CheckStatus,
    check_config,
    check_github_ssh,
    check_system_tools,
    check_tool_versions,
    list_venvs,
    run_doctor,
)
from trobz_local.main import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# check_config
# ---------------------------------------------------------------------------


def test_check_config_valid(tmp_path):
    (tmp_path / "config.toml").write_text('versions = ["18.0"]\n\n[repos]\nodoo = ["odoo"]\n')
    result = check_config(tmp_path)
    assert result.status == CheckStatus.OK
    assert "1 version" in result.message


def test_check_config_missing(tmp_path):
    result = check_config(tmp_path)
    assert result.status == CheckStatus.WARN
    assert "Not found" in result.message


def test_check_config_invalid_toml(tmp_path):
    (tmp_path / "config.toml").write_text("invalid [[ toml")
    result = check_config(tmp_path)
    assert result.status == CheckStatus.FAIL
    assert "Invalid TOML" in result.message


def test_check_config_bad_schema(tmp_path):
    (tmp_path / "config.toml").write_text('versions = ["not-a-version!!"]')
    result = check_config(tmp_path)
    assert result.status == CheckStatus.FAIL
    assert "Schema validation" in result.message or "failed" in result.message.lower()


# ---------------------------------------------------------------------------
# check_github_ssh
# ---------------------------------------------------------------------------


@patch("trobz_local.doctor.shutil.which", return_value=None)
def test_check_github_ssh_no_binary(mock_which):
    result = check_github_ssh()
    assert result.status == CheckStatus.FAIL
    assert "not found" in result.message.lower()


@patch("trobz_local.doctor.shutil.which", return_value="/usr/bin/ssh")
@patch("trobz_local.doctor.subprocess.run")
def test_check_github_ssh_ok(mock_run, mock_which):
    mock_run.return_value = MagicMock(
        returncode=1,
        stderr="Hi user! You've successfully authenticated, but GitHub does not provide shell access.",
    )
    result = check_github_ssh()
    assert result.status == CheckStatus.OK
    assert result.message == "Authenticated"


@patch("trobz_local.doctor.shutil.which", return_value="/usr/bin/ssh")
@patch("trobz_local.doctor.subprocess.run")
def test_check_github_ssh_fail(mock_run, mock_which):
    mock_run.return_value = MagicMock(
        returncode=255,
        stderr="Permission denied (publickey).",
    )
    result = check_github_ssh()
    assert result.status == CheckStatus.FAIL


@patch("trobz_local.doctor.shutil.which", return_value="/usr/bin/ssh")
@patch("trobz_local.doctor.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ssh", timeout=8))
def test_check_github_ssh_timeout(mock_run, mock_which):
    result = check_github_ssh()
    assert result.status == CheckStatus.WARN
    assert "timeout" in result.message.lower()


# ---------------------------------------------------------------------------
# check_system_tools
# ---------------------------------------------------------------------------


@patch("trobz_local.doctor.shutil.which", return_value="/usr/bin/git")
@patch("trobz_local.doctor.subprocess.run")
def test_check_system_tools_all_found(mock_run, mock_which):
    mock_run.return_value = MagicMock(stdout="git version 2.45.0", stderr="", returncode=0)
    results = check_system_tools()
    assert len(results) == 5  # uv, gh, git, npm, psql
    assert all(r.status == CheckStatus.OK for r in results)


@patch("trobz_local.doctor.shutil.which", return_value=None)
def test_check_system_tools_none_found(mock_which):
    results = check_system_tools()
    assert len(results) == 5
    assert all(r.status == CheckStatus.WARN for r in results)
    assert all("Not found" in r.message for r in results)


@patch("trobz_local.doctor.shutil.which", side_effect=lambda t: "/usr/bin/git" if t == "git" else None)
@patch("trobz_local.doctor.subprocess.run")
def test_check_system_tools_partial(mock_run, mock_which):
    mock_run.return_value = MagicMock(stdout="git version 2.45.0", stderr="", returncode=0)
    results = check_system_tools()
    found = [r for r in results if r.status == CheckStatus.OK]
    missing = [r for r in results if r.status == CheckStatus.WARN]
    assert len(found) == 1
    assert found[0].name == "git"
    assert len(missing) == 4


# ---------------------------------------------------------------------------
# check_tool_versions — uv tools
# ---------------------------------------------------------------------------


@patch("trobz_local.doctor.shutil.which", return_value=None)
def test_check_uv_tools_no_uv(mock_which):
    results = check_tool_versions({"uv": ["ruff"], "npm": []})
    assert len(results) == 1
    assert results[0].status == CheckStatus.WARN
    assert "uv not found" in results[0].message


@patch("trobz_local.doctor.shutil.which", return_value="/usr/bin/uv")
@patch("trobz_local.doctor.subprocess.run")
def test_check_uv_tools_found(mock_run, mock_which):
    mock_run.return_value = MagicMock(stdout="ruff v0.11.5\nodoo-venv v1.0.0\n", returncode=0)
    results = check_tool_versions({"uv": ["ruff", "odoo-venv"], "npm": []})
    assert all(r.status == CheckStatus.OK for r in results)
    assert "0.11.5" in results[0].message


@patch("trobz_local.doctor.shutil.which", return_value="/usr/bin/uv")
@patch("trobz_local.doctor.subprocess.run")
def test_check_uv_tools_missing(mock_run, mock_which):
    mock_run.return_value = MagicMock(stdout="", returncode=0)
    results = check_tool_versions({"uv": ["ruff"], "npm": []})
    assert results[0].status == CheckStatus.WARN
    assert "Not installed" in results[0].message


# ---------------------------------------------------------------------------
# check_tool_versions — npm packages
# ---------------------------------------------------------------------------


@patch("trobz_local.doctor.shutil.which", side_effect=lambda t: None if t == "npm" else "/usr/bin/uv")
def test_check_npm_no_npm(mock_which):
    results = check_tool_versions({"uv": [], "npm": ["rtlcss"]})
    assert len(results) == 1
    assert results[0].status == CheckStatus.WARN
    assert "npm not found" in results[0].message


@patch("trobz_local.doctor.shutil.which", return_value="/usr/bin/npm")
@patch("trobz_local.doctor.subprocess.run")
def test_check_npm_packages_installed(mock_run, mock_which):
    import json

    mock_run.return_value = MagicMock(
        stdout=json.dumps({"dependencies": {"rtlcss": {"version": "4.3.0"}}}),
        returncode=0,
    )
    results = check_tool_versions({"uv": [], "npm": ["rtlcss"]})
    assert results[0].status == CheckStatus.OK
    assert "4.3.0" in results[0].message


@patch("trobz_local.doctor.shutil.which", return_value="/usr/bin/npm")
@patch("trobz_local.doctor.subprocess.run")
def test_check_npm_packages_missing(mock_run, mock_which):
    import json

    mock_run.return_value = MagicMock(
        stdout=json.dumps({"dependencies": {}}),
        returncode=0,
    )
    results = check_tool_versions({"uv": [], "npm": ["rtlcss"]})
    assert results[0].status == CheckStatus.WARN
    assert "Not installed" in results[0].message


# ---------------------------------------------------------------------------
# list_venvs
# ---------------------------------------------------------------------------


def test_list_venvs_no_dir(tmp_path):
    results = list_venvs(tmp_path, ["18.0"])
    assert results[0].status == CheckStatus.WARN
    assert "does not exist" in results[0].message


def test_list_venvs_missing_version(tmp_path):
    (tmp_path / "venvs").mkdir()
    results = list_venvs(tmp_path, ["18.0"])
    assert results[0].status == CheckStatus.WARN
    assert "Not created" in results[0].message


@patch("trobz_local.doctor.subprocess.run")
def test_list_venvs_found(mock_run, tmp_path):
    venv_bin = tmp_path / "venvs" / "18.0" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").touch()
    mock_run.return_value = MagicMock(stdout="Python 3.12.3", returncode=0)
    results = list_venvs(tmp_path, ["18.0"])
    assert results[0].status == CheckStatus.OK
    assert "3.12.3" in results[0].message


def test_list_venvs_missing_python_bin(tmp_path):
    venv_dir = tmp_path / "venvs" / "18.0"
    venv_dir.mkdir(parents=True)
    results = list_venvs(tmp_path, ["18.0"])
    assert results[0].status == CheckStatus.WARN
    assert "bin/python" in results[0].message


def test_list_venvs_empty_versions(tmp_path):
    (tmp_path / "venvs").mkdir()
    results = list_venvs(tmp_path, [])
    assert results == []


# ---------------------------------------------------------------------------
# run_doctor orchestrator
# ---------------------------------------------------------------------------


@patch("trobz_local.doctor.check_github_ssh")
@patch("trobz_local.doctor.check_system_tools")
@patch("trobz_local.doctor.check_tool_versions")
@patch("trobz_local.doctor.list_venvs")
def test_run_doctor_with_config(mock_venvs, mock_tools, mock_sys_tools, mock_ssh, tmp_path):
    (tmp_path / "config.toml").write_text('versions = ["18.0"]\n')
    mock_ssh.return_value = CheckResult("GitHub SSH", CheckStatus.OK, "Authenticated")
    mock_sys_tools.return_value = [CheckResult("git", CheckStatus.OK, "Found (git version 2.45.0)")]
    mock_tools.return_value = []
    mock_venvs.return_value = []

    groups = run_doctor(tmp_path)

    assert "Configuration" in groups
    assert "Connectivity" in groups
    assert "Tools" in groups
    assert "Virtual Environments" in groups
    assert groups["Configuration"][0].status == CheckStatus.OK
    # System tools always included
    assert groups["Tools"][0].name == "git"


@patch("trobz_local.doctor.check_github_ssh")
@patch("trobz_local.doctor.check_system_tools")
def test_run_doctor_no_config(mock_sys_tools, mock_ssh, tmp_path):
    mock_ssh.return_value = CheckResult("GitHub SSH", CheckStatus.WARN, "Timeout")
    mock_sys_tools.return_value = [CheckResult("uv", CheckStatus.OK, "Found")]
    groups = run_doctor(tmp_path)

    assert "Configuration" in groups
    assert groups["Configuration"][0].status == CheckStatus.WARN
    assert "Connectivity" in groups
    # System tools always present
    assert "Tools" in groups
    assert groups["Tools"][0].name == "uv"


# ---------------------------------------------------------------------------
# CLI command: doctor
# ---------------------------------------------------------------------------


@patch("trobz_local.main.run_doctor")
@patch("trobz_local.main.get_code_root")
def test_doctor_command_all_ok(mock_root, mock_doctor, tmp_path):
    mock_root.return_value = tmp_path
    mock_doctor.return_value = {
        "Configuration": [CheckResult("Config file", CheckStatus.OK, "Valid")],
    }
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "OK" in result.output
    assert "Summary" in result.output


@patch("trobz_local.main.run_doctor")
@patch("trobz_local.main.get_code_root")
def test_doctor_command_has_failure(mock_root, mock_doctor, tmp_path):
    mock_root.return_value = tmp_path
    mock_doctor.return_value = {
        "Tools": [CheckResult("uv: ruff", CheckStatus.FAIL, "Not installed")],
    }
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "FAIL" in result.output


@patch("trobz_local.main.run_doctor")
@patch("trobz_local.main.get_code_root")
def test_doctor_command_warnings_exit_zero(mock_root, mock_doctor, tmp_path):
    mock_root.return_value = tmp_path
    mock_doctor.return_value = {
        "Tools": [CheckResult("uv: ruff", CheckStatus.WARN, "Not installed")],
    }
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "!!" in result.output
