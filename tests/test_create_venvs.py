import re
from unittest.mock import MagicMock, patch

import pytest
from rich.progress import Progress, TaskID
from typer.testing import CliRunner

from trobz_local.concurrency import TaskResult
from trobz_local.main import _create_venvs, app
from trobz_local.utils import ConfigModel, get_config

runner = CliRunner()
task = TaskID(0)


@pytest.fixture
def mock_config(tmp_path):
    config_content = """
versions = ["16.0", "17.0"]
"""
    config_path = tmp_path / "code" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_content)

    with patch("trobz_local.utils.Path.home", return_value=tmp_path):
        yield get_config()


@pytest.fixture(autouse=True)
def mock_get_uv_path():
    with patch("trobz_local.utils.get_uv_path", return_value="uv") as mock_uv:
        yield mock_uv


@pytest.fixture(autouse=True)
def mock_typer_confirm():
    with patch("typer.confirm", return_value=True) as mock_tc:
        yield mock_tc


def test_create_venv_success(tmp_path, mock_get_uv_path):
    progress_mock = MagicMock(spec=Progress)
    version = "16.0"
    uv_path = "uv"
    odoo_dir_base = tmp_path / "code" / "odoo" / "odoo"
    venv_dir_base = tmp_path / "code" / "venvs"

    with patch("subprocess.run") as mock_subprocess_run:
        _create_venvs(progress_mock, task, version, uv_path, odoo_dir_base, venv_dir_base)

        expected_cmd = [
            uv_path,
            "tool",
            "run",
            "odoo-venv",
            "create",
            version,
            "--odoo-dir",
            str(odoo_dir_base / version),
            "--venv-dir",
            str(venv_dir_base / version),
            "--preset",
            "local",
            "--verbose",
            "--create-launcher",
        ]
        mock_subprocess_run.assert_called_once_with(
            expected_cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        progress_mock.update.assert_any_call(
            task, description=f"Creating venv for {version}...", total=100, completed=0, start=True
        )
        progress_mock.update.assert_any_call(task, description=f"✓ Venv for {version} created.", completed=100)


def test_create_venv_failure(tmp_path, mock_get_uv_path):
    progress_mock = MagicMock(spec=Progress)
    version = "16.0"
    uv_path = "uv"
    odoo_dir_base = tmp_path / "code" / "odoo" / "odoo"
    venv_dir_base = tmp_path / "code" / "venvs"

    with patch("subprocess.run", side_effect=Exception("Test Error")):
        with pytest.raises(Exception, match="Test Error"):
            _create_venvs(progress_mock, task, version, uv_path, odoo_dir_base, venv_dir_base)

        found_error_description = False
        for call_args in progress_mock.update.call_args_list:
            if "description" in call_args.kwargs:
                actual_description = call_args.kwargs["description"]
                if re.search(r"\[red\]✗ Error venv 16\.0: Test Error", actual_description):
                    found_error_description = True
                    break
        assert found_error_description


def test_create_venv_without_launcher(tmp_path, mock_get_uv_path):
    """When create_launcher=False, --create-launcher is not in the command."""
    progress_mock = MagicMock(spec=Progress)
    version = "16.0"
    uv_path = "uv"
    odoo_dir_base = tmp_path / "code" / "odoo" / "odoo"
    venv_dir_base = tmp_path / "code" / "venvs"

    with patch("subprocess.run") as mock_subprocess_run:
        _create_venvs(progress_mock, task, version, uv_path, odoo_dir_base, venv_dir_base, create_launcher=False)

        called_cmd = mock_subprocess_run.call_args[0][0]
        assert "--create-launcher" not in called_cmd


def test_config_model_create_launcher_default():
    """ConfigModel defaults create_launcher to True when omitted."""
    model = ConfigModel(versions=["18.0"])
    assert model.create_launcher is True


def test_config_model_create_launcher_false():
    """ConfigModel accepts create_launcher = false."""
    model = ConfigModel(versions=["18.0"], create_launcher=False)
    assert model.create_launcher is False


def test_create_venvs_calls_run_tasks_correctly(tmp_path, mock_config, mock_typer_confirm):
    mock_results = [
        TaskResult(success=True, name="venv-16.0", message="Completed"),
        TaskResult(success=True, name="venv-17.0", message="Completed"),
    ]
    with (
        patch("trobz_local.main.run_tasks", return_value=mock_results) as mock_run_tasks,
        patch(
            "trobz_local.utils.get_config",
            return_value={"versions": ["16.0", "17.0"], "repos": {}, "tools": {}, "create_launcher": True},
        ),
        patch("trobz_local.utils.get_uv_path", return_value="mock_uv_path"),
    ):
        result = runner.invoke(app, ["create-venvs"])

        assert result.exit_code == 0
        mock_run_tasks.assert_called_once()

        called_args, called_kwargs = mock_run_tasks.call_args
        concurrency_tasks_arg = called_args[0]

        assert len(concurrency_tasks_arg) == 2
        assert concurrency_tasks_arg[0]["name"] == "venv-16.0"
        assert concurrency_tasks_arg[0]["func"] == _create_venvs
        assert "uv_path" in concurrency_tasks_arg[0]["args"]
        assert concurrency_tasks_arg[1]["name"] == "venv-17.0"

        assert called_kwargs.get("max_workers", 4) == 4
