"""Tests for ensure-db-user command and postgres module."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from trobz_local.main import app
from trobz_local.postgres import (
    check_postgres_running,
    check_user_exists,
    create_user,
    validate_password,
    validate_username,
    verify_connection,
)

runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_typer_confirm():
    with patch("typer.confirm", return_value=True) as mock_tc:
        yield mock_tc


# =============================================================================
# Validation Tests
# =============================================================================


@pytest.mark.parametrize("username", ["odoo", "test_user", "_user", "a" * 63])
def test_validate_username_valid(username):
    assert validate_username(username) is True


@pytest.mark.parametrize("username", ["", "123abc", "a" * 64, None, "user-name", "user.name"])
def test_validate_username_invalid(username):
    assert validate_username(username) is False


def test_validate_password_valid():
    assert validate_password("odoo") is True
    assert validate_password("complex_password_123") is True


@pytest.mark.parametrize("password", ["", None])
def test_validate_password_invalid(password):
    assert validate_password(password) is False


# =============================================================================
# check_postgres_running Tests
# =============================================================================


@patch("trobz_local.postgres.shutil.which")
@patch("trobz_local.postgres.subprocess.run")
def test_pg_running_success(mock_run, mock_which):
    mock_which.return_value = "/usr/bin/pg_isready"
    mock_run.return_value = MagicMock(returncode=0)
    assert check_postgres_running() is True


@patch("trobz_local.postgres.shutil.which")
@patch("trobz_local.postgres.subprocess.run")
def test_pg_running_not_running(mock_run, mock_which):
    mock_which.return_value = "/usr/bin/pg_isready"
    mock_run.return_value = MagicMock(returncode=2)
    assert check_postgres_running() is False


@patch("trobz_local.postgres.shutil.which")
@patch("trobz_local.postgres.subprocess.run")
def test_pg_running_timeout(mock_run, mock_which):
    mock_which.return_value = "/usr/bin/pg_isready"
    mock_run.side_effect = subprocess.TimeoutExpired("pg_isready", 5)
    assert check_postgres_running() is False


@patch("trobz_local.postgres.shutil.which")
def test_pg_running_not_installed(mock_which):
    mock_which.return_value = None
    assert check_postgres_running() is False


# =============================================================================
# check_user_exists Tests
# =============================================================================


@patch("trobz_local.postgres.subprocess.run")
def test_user_exists_linux(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="1\n")
    assert check_user_exists("odoo", "Linux") is True
    # Verify sudo command was used
    args = mock_run.call_args[0][0]
    assert args[0:3] == ["sudo", "-n", "-u"]


@patch("trobz_local.postgres.shutil.which")
@patch("trobz_local.postgres.subprocess.run")
def test_user_exists_macos(mock_run, mock_which):
    mock_which.return_value = "/usr/local/bin/psql"
    mock_run.return_value = MagicMock(returncode=0, stdout="1\n")
    assert check_user_exists("odoo", "Darwin") is True
    # Verify direct psql command was used (no sudo)
    args = mock_run.call_args[0][0]
    assert "sudo" not in args


@patch("trobz_local.postgres.subprocess.run")
def test_user_not_exists(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="")
    assert check_user_exists("odoo", "Linux") is False


def test_user_exists_invalid_username():
    # Should return False without making subprocess call
    assert check_user_exists("", "Linux") is False
    assert check_user_exists("123invalid", "Linux") is False


# =============================================================================
# create_user Tests
# =============================================================================


@patch("trobz_local.postgres.subprocess.run")
def test_create_user_linux_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stderr="")
    success, error = create_user("odoo", "odoo", "Linux")
    assert success is True
    assert error == ""
    # Verify sudo command
    args = mock_run.call_args[0][0]
    assert args[0:3] == ["sudo", "-n", "-u"]


@patch("trobz_local.postgres.shutil.which")
@patch("trobz_local.postgres.subprocess.run")
def test_create_user_macos_success(mock_run, mock_which):
    mock_which.return_value = "/usr/local/bin/psql"
    mock_run.return_value = MagicMock(returncode=0, stderr="")
    success, error = create_user("odoo", "odoo", "Darwin")
    assert success is True
    assert error == ""
    # Verify no sudo
    args = mock_run.call_args[0][0]
    assert "sudo" not in args


@patch("trobz_local.postgres.subprocess.run")
def test_create_user_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stderr="ERROR: permission denied")
    success, error = create_user("odoo", "odoo", "Linux")
    assert success is False
    assert "permission denied" in error


def test_create_user_invalid_input():
    success, error = create_user("", "odoo", "Linux")
    assert success is False
    assert "Invalid" in error

    success, error = create_user("odoo", "", "Linux")
    assert success is False
    assert "Invalid" in error


@patch("trobz_local.postgres.subprocess.run")
def test_create_user_timeout(mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired("psql", 10)
    success, error = create_user("odoo", "odoo", "Linux")
    assert success is False
    assert "timed out" in error


# =============================================================================
# verify_connection Tests
# =============================================================================


@patch("trobz_local.postgres.shutil.which")
@patch("trobz_local.postgres.subprocess.run")
def test_verify_connection_success(mock_run, mock_which):
    mock_which.return_value = "/usr/local/bin/psql"
    mock_run.return_value = MagicMock(returncode=0)
    assert verify_connection("localhost", "odoo", "odoo") is True
    # Verify PGPASSWORD was set in env
    env = mock_run.call_args[1]["env"]
    assert "PGPASSWORD" in env
    assert env["PGPASSWORD"] == "odoo"


@patch("trobz_local.postgres.shutil.which")
@patch("trobz_local.postgres.subprocess.run")
def test_verify_connection_failure(mock_run, mock_which):
    mock_which.return_value = "/usr/local/bin/psql"
    mock_run.return_value = MagicMock(returncode=2)
    assert verify_connection("localhost", "odoo", "odoo") is False


@patch("trobz_local.postgres.shutil.which")
def test_verify_connection_psql_not_found(mock_which):
    mock_which.return_value = None
    assert verify_connection("localhost", "odoo", "odoo") is False


# =============================================================================
# CLI Integration Tests
# =============================================================================


@patch("trobz_local.main.get_os_info")
@patch("trobz_local.main.check_postgres_running")
def test_ensure_db_user_pg_not_running(mock_check_pg, mock_get_os):
    mock_get_os.return_value = {"system": "Linux"}
    mock_check_pg.return_value = False

    result = runner.invoke(app, ["--no-newcomer", "ensure-db-user"])

    assert result.exit_code == 1
    assert "PostgreSQL is not running" in result.stdout


@patch("trobz_local.main.get_os_info")
@patch("trobz_local.main.check_postgres_running")
def test_ensure_db_user_pg_not_running_macos(mock_check_pg, mock_get_os):
    mock_get_os.return_value = {"system": "Darwin"}
    mock_check_pg.return_value = False

    result = runner.invoke(app, ["--no-newcomer", "ensure-db-user"])

    assert result.exit_code == 1
    assert "brew services start postgresql" in result.stdout


@patch("trobz_local.main.get_os_info")
@patch("trobz_local.main.check_postgres_running")
def test_ensure_db_user_pg_not_running_linux(mock_check_pg, mock_get_os):
    mock_get_os.return_value = {"system": "Linux"}
    mock_check_pg.return_value = False

    result = runner.invoke(app, ["--no-newcomer", "ensure-db-user"])

    assert result.exit_code == 1
    assert "sudo systemctl start postgresql" in result.stdout


@patch("trobz_local.main.get_os_info")
@patch("trobz_local.main.verify_connection")
@patch("trobz_local.main.check_user_exists")
@patch("trobz_local.main.check_postgres_running")
def test_ensure_db_user_user_exists(mock_check_pg, mock_check_user, mock_test_conn, mock_get_os):
    mock_get_os.return_value = {"system": "Linux"}
    mock_check_pg.return_value = True
    mock_check_user.return_value = True
    mock_test_conn.return_value = True

    result = runner.invoke(app, ["--no-newcomer", "ensure-db-user"])

    assert result.exit_code == 0
    assert "already exists" in result.stdout
    assert "Connection successful" in result.stdout


@patch("trobz_local.main.get_os_info")
@patch("trobz_local.main.verify_connection")
@patch("trobz_local.main.create_user")
@patch("trobz_local.main.check_user_exists")
@patch("trobz_local.main.check_postgres_running")
def test_ensure_db_user_create_success(mock_check_pg, mock_check_user, mock_create, mock_test_conn, mock_get_os):
    mock_get_os.return_value = {"system": "Linux"}
    mock_check_pg.return_value = True
    mock_check_user.return_value = False
    mock_create.return_value = (True, "")
    mock_test_conn.return_value = True

    result = runner.invoke(app, ["--no-newcomer", "ensure-db-user"])

    assert result.exit_code == 0
    assert "created successfully" in result.stdout


@patch("trobz_local.main.get_os_info")
@patch("trobz_local.main.create_user")
@patch("trobz_local.main.check_user_exists")
@patch("trobz_local.main.check_postgres_running")
def test_ensure_db_user_create_failure(mock_check_pg, mock_check_user, mock_create, mock_get_os):
    mock_get_os.return_value = {"system": "Linux"}
    mock_check_pg.return_value = True
    mock_check_user.return_value = False
    mock_create.return_value = (False, "permission denied")

    result = runner.invoke(app, ["--no-newcomer", "ensure-db-user"])

    assert result.exit_code == 1
    assert "Failed to create user" in result.stdout


@patch("trobz_local.main.get_os_info")
@patch("trobz_local.main.create_user")
@patch("trobz_local.main.check_user_exists")
@patch("trobz_local.main.check_postgres_running")
def test_ensure_db_user_create_failure_linux_sudo(mock_check_pg, mock_check_user, mock_create, mock_get_os):
    mock_get_os.return_value = {"system": "Linux"}
    mock_check_pg.return_value = True
    mock_check_user.return_value = False
    mock_create.return_value = (False, "sudo: no tty present")

    result = runner.invoke(app, ["--no-newcomer", "ensure-db-user"])

    assert result.exit_code == 1
    assert "Manual instructions" in result.stdout
    assert "sudo -u postgres createuser" in result.stdout


@patch("trobz_local.main.get_os_info")
@patch("trobz_local.main.verify_connection")
@patch("trobz_local.main.create_user")
@patch("trobz_local.main.check_user_exists")
@patch("trobz_local.main.check_postgres_running")
def test_ensure_db_user_connection_failure(mock_check_pg, mock_check_user, mock_create, mock_test_conn, mock_get_os):
    mock_get_os.return_value = {"system": "Linux"}
    mock_check_pg.return_value = True
    mock_check_user.return_value = False
    mock_create.return_value = (True, "")
    mock_test_conn.return_value = False

    result = runner.invoke(app, ["--no-newcomer", "ensure-db-user"])

    assert result.exit_code == 1
    assert "Connection test failed" in result.stdout
