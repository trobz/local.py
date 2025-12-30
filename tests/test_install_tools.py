from unittest.mock import call, patch

from typer.testing import CliRunner

from trobz_local.main import app

runner = CliRunner()


@patch("trobz_local.utils.shutil.which")
@patch("trobz_local.main.get_config")
@patch("trobz_local.main.subprocess.run")
def test_install_tools(mock_subprocess, mock_get_config, mock_which):
    mock_which.return_value = "/usr/bin/uv"
    mock_get_config.return_value = {"tools": ["invoke", "git-aggregator"]}

    result = runner.invoke(app, ["--no-newcomer", "install-tools"])

    assert result.exit_code == 0
    assert mock_subprocess.call_count == 2

    expected_calls = [
        call(["/usr/bin/uv", "tool", "install", "--", "invoke"], check=True, capture_output=True, text=True),
        call(["/usr/bin/uv", "tool", "install", "--", "git-aggregator"], check=True, capture_output=True, text=True),
    ]
    mock_subprocess.assert_has_calls(expected_calls)


@patch("trobz_local.utils.shutil.which")
@patch("trobz_local.main.get_config")
@patch("trobz_local.main.subprocess.run")
def test_install_tools_empty_config(mock_subprocess, mock_get_config, mock_which):
    mock_which.return_value = "/usr/bin/uv"
    mock_get_config.return_value = {}  # No tools key

    result = runner.invoke(app, ["--no-newcomer", "install-tools"])

    assert result.exit_code == 0
    mock_subprocess.assert_not_called()

    mock_get_config.return_value = {"tools": []}  # Empty tools list
    result = runner.invoke(app, ["--no-newcomer", "install-tools"])

    assert result.exit_code == 0
    mock_subprocess.assert_not_called()


@patch("trobz_local.utils.shutil.which")
@patch("trobz_local.main.get_config")
@patch("trobz_local.main.subprocess.run")
def test_install_tools_uv_missing(mock_subprocess, mock_get_config, mock_which):
    mock_which.return_value = None  # uv not found
    mock_get_config.return_value = {"tools": ["invoke"]}

    result = runner.invoke(app, ["--no-newcomer", "install-tools"])

    assert result.exit_code == 1
    assert "uv is not installed" in result.stdout
    mock_subprocess.assert_not_called()
