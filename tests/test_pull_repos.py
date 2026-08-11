from unittest.mock import MagicMock, create_autospec, patch

import git
import pytest
from rich.progress import Progress, TaskID
from typer.testing import CliRunner

from trobz_local.main import ODOO_URLS, _get_tasks, _pull_repo
from trobz_local.utils import get_config

runner = CliRunner()

task = TaskID(0)


@pytest.fixture
def mock_config(tmp_path):
    config_content = """
versions = ["16.0", "17.0"]

[repos]
odoo = ["odoo"]
oca = ["server-tools"]
"""
    config_path = tmp_path / "code" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_content)

    with patch("trobz_local.utils.Path.home", return_value=tmp_path):
        yield get_config()


@pytest.fixture(autouse=True)
def mock_main_git_progress():
    with patch("trobz_local.main.GitProgress") as mock_gp:
        mock_gp.return_value = MagicMock()
        yield mock_gp


@pytest.fixture(autouse=True)
def mock_git_repo_calls():
    with patch("trobz_local.main.git") as mock_git_module:
        mock_git_module.exc = git.exc

        mock_repo_instance = create_autospec(git.Repo, instance=True)

        mock_git_module.Repo.clone_from = create_autospec(git.Repo.clone_from)

        mock_git_module.Repo.return_value = mock_repo_instance

        mock_repo_instance.remotes.origin.fetch.return_value = MagicMock(spec=git.Remote.fetch)
        mock_repo_instance.heads.__getitem__.return_value.checkout.return_value = None
        mock_repo_instance.git.reset.return_value = None

        yield mock_git_module.Repo.clone_from, mock_git_module.Repo


@pytest.fixture(autouse=True)
def mock_typer_confirm():
    with patch("typer.confirm", return_value=True) as mock_tc:
        yield mock_tc


def test_pull_repo_clones_new_repo(tmp_path, mock_git_repo_calls, mock_main_git_progress):
    mock_clone_from, _ = mock_git_repo_calls
    progress_mock = MagicMock(spec=Progress)

    repo_path = tmp_path / "code" / "odoo" / "odoo" / "16.0"
    repo_path.parent.mkdir(parents=True, exist_ok=True)

    repo_info = {
        "repo_name": "odoo",
        "repo_path": repo_path,
        "repo_url": ODOO_URLS["odoo"],
        "version": "16.0",
    }

    assert not repo_path.exists()

    _pull_repo(progress_mock, task, repo_info)

    mock_clone_from.assert_called_once_with(
        ODOO_URLS["odoo"],
        to_path=repo_path,
        branch="16.0",
        progress=mock_main_git_progress.return_value,
        depth=1,
    )
    progress_mock.update.assert_any_call(task, description="Cloning odoo (16.0)")
    progress_mock.update.assert_any_call(task, description="✓ odoo (16.0) updated.", completed=100, total=100)


def test_pull_repo_fetches_existing_repo(tmp_path, mock_git_repo_calls, mock_main_git_progress):
    _, mock_repo_class = mock_git_repo_calls
    progress_mock = MagicMock(spec=Progress)

    repo_path = tmp_path / "code" / "odoo" / "odoo" / "16.0"
    repo_path.mkdir(parents=True, exist_ok=True)

    repo_info = {
        "repo_name": "odoo",
        "repo_path": repo_path,
        "repo_url": ODOO_URLS["odoo"],
        "version": "16.0",
    }

    _pull_repo(progress_mock, task, repo_info)

    mock_git_repo_calls[0].assert_not_called()
    mock_repo_class.assert_called_once_with(repo_path)
    mock_repo_class.return_value.remotes.origin.fetch.assert_called_once_with("16.0")
    mock_repo_class.return_value.heads.__getitem__.assert_called_once_with("16.0")
    mock_repo_class.return_value.heads.__getitem__.return_value.checkout.return_value = None
    mock_repo_class.return_value.git.reset.assert_called_once_with("--hard", "origin/16.0")
    progress_mock.update.assert_any_call(task, description="Fetching odoo (16.0)")
    progress_mock.update.assert_any_call(task, description="✓ odoo (16.0) updated.", completed=100, total=100)


def test_pull_repo_handles_git_exception(tmp_path, mock_git_repo_calls):
    mock_clone_from, _ = mock_git_repo_calls
    mock_clone_from.side_effect = git.exc.GitCommandError("git", 1, stderr="Permission denied")
    progress_mock = MagicMock(spec=Progress)

    repo_path = tmp_path / "code" / "odoo" / "odoo" / "16.0"
    repo_path.parent.mkdir(parents=True, exist_ok=True)

    repo_info = {
        "repo_name": "odoo",
        "repo_path": repo_path,
        "repo_url": ODOO_URLS["odoo"],
        "version": "16.0",
    }

    with pytest.raises(git.exc.GitCommandError):
        _pull_repo(progress_mock, task, repo_info)

    found_error_description = False
    for call_args in progress_mock.update.call_args_list:
        if "description" in call_args.kwargs:
            actual_description = call_args.kwargs["description"]
            if "[red]✗ Error odoo (16.0): stderr: 'Permission denied'" in actual_description:
                found_error_description = True
                break
    assert found_error_description


def test_pull_repo_clones_with_shallow_clone_by_default(tmp_path, mock_git_repo_calls, mock_main_git_progress):
    """Test that repos are cloned with depth=1 by default."""
    mock_clone_from, _ = mock_git_repo_calls
    progress_mock = MagicMock(spec=Progress)

    repo_path = tmp_path / "code" / "odoo" / "odoo" / "16.0"
    repo_path.parent.mkdir(parents=True, exist_ok=True)

    repo_info = {
        "repo_name": "odoo",
        "repo_path": repo_path,
        "repo_url": ODOO_URLS["odoo"],
        "version": "16.0",
    }

    # Call without full_history parameter (default behavior)
    _pull_repo(progress_mock, task, repo_info)

    # Verify depth=1 is used
    mock_clone_from.assert_called_once()
    call_kwargs = mock_clone_from.call_args.kwargs
    assert call_kwargs["depth"] == 1


def test_pull_repo_clones_with_full_history_when_flag_set(tmp_path, mock_git_repo_calls, mock_main_git_progress):
    """Test that repos are cloned with full history when --full-history flag is used."""
    mock_clone_from, _ = mock_git_repo_calls
    progress_mock = MagicMock(spec=Progress)

    repo_path = tmp_path / "code" / "odoo" / "odoo" / "16.0"
    repo_path.parent.mkdir(parents=True, exist_ok=True)

    repo_info = {
        "repo_name": "odoo",
        "repo_path": repo_path,
        "repo_url": ODOO_URLS["odoo"],
        "version": "16.0",
    }

    # Call with full_history=True
    _pull_repo(progress_mock, task, repo_info, full_history=True)

    # Verify depth=None is used (full clone)
    mock_clone_from.assert_called_once()
    call_kwargs = mock_clone_from.call_args.kwargs
    assert call_kwargs["depth"] is None


def test_pull_repo_update_existing_ignores_full_history_flag(tmp_path, mock_git_repo_calls, mock_main_git_progress):
    """Test that existing repo updates ignore the full_history flag."""
    _, mock_repo_class = mock_git_repo_calls
    progress_mock = MagicMock(spec=Progress)

    repo_path = tmp_path / "code" / "odoo" / "odoo" / "16.0"
    repo_path.mkdir(parents=True, exist_ok=True)

    repo_info = {
        "repo_name": "odoo",
        "repo_path": repo_path,
        "repo_url": ODOO_URLS["odoo"],
        "version": "16.0",
    }

    # Call with full_history=True on existing repo
    _pull_repo(progress_mock, task, repo_info, full_history=True)

    # Verify fetch/reset was called (not clone)
    mock_repo_instance = mock_repo_class.return_value
    mock_repo_instance.remotes.origin.fetch.assert_called_once_with("16.0")
    mock_repo_instance.git.reset.assert_called_once_with("--hard", "origin/16.0")


def test_get_tasks_generates_correct_list(mock_config, tmp_path):
    odoo_versions = ["16.0", "17.0"]
    repos_config = {"odoo": ["odoo"], "oca": ["server-tools"]}
    code_root = tmp_path / "code"

    tasks = _get_tasks(odoo_versions, repos_config, code_root, None)

    expected_tasks = [
        {
            "repo_name": "odoo",
            "repo_path": code_root / "odoo" / "odoo" / "16.0",
            "repo_url": ODOO_URLS["odoo"],
            "version": "16.0",
        },
        {
            "repo_name": "server-tools",
            "repo_path": code_root / "oca" / "16.0" / "server-tools",
            "repo_url": "git@github.com:oca/server-tools.git",
            "version": "16.0",
        },
        {
            "repo_name": "odoo",
            "repo_path": code_root / "odoo" / "odoo" / "17.0",
            "repo_url": ODOO_URLS["odoo"],
            "version": "17.0",
        },
        {
            "repo_name": "server-tools",
            "repo_path": code_root / "oca" / "17.0" / "server-tools",
            "repo_url": "git@github.com:oca/server-tools.git",
            "version": "17.0",
        },
    ]
    for task in tasks:
        task["repo_path"] = str(task["repo_path"])
    for task in expected_tasks:
        task["repo_path"] = str(task["repo_path"])

    tasks_sorted = sorted(tasks, key=lambda x: (x["repo_name"], x["version"]))
    expected_tasks_sorted = sorted(expected_tasks, key=lambda x: (x["repo_name"], x["version"]))

    assert tasks_sorted == expected_tasks_sorted


def test_get_tasks_with_filter(mock_config, tmp_path):
    odoo_versions = ["16.0"]
    repos_config = {"odoo": ["odoo"], "oca": ["server-tools"]}
    code_root = tmp_path / "code"

    tasks = _get_tasks(odoo_versions, repos_config, code_root, repo_filter=["odoo"])

    expected_tasks = [
        {
            "repo_name": "odoo",
            "repo_path": code_root / "odoo" / "odoo" / "16.0",
            "repo_url": ODOO_URLS["odoo"],
            "version": "16.0",
        },
    ]
    for task in tasks:
        task["repo_path"] = str(task["repo_path"])
    for task in expected_tasks:
        task["repo_path"] = str(task["repo_path"])

    assert tasks == expected_tasks


def test_get_tasks_inline_branch_override(mock_config, tmp_path):
    odoo_versions = ["17.0", "18.0"]
    repos_config = {
        "oca": [
            "server-tools",
            ["oca-port", ["main"]],
            ["oca-custom", ["17.0", "18.0"]],
        ]
    }
    code_root = tmp_path / "code"

    tasks = _get_tasks(odoo_versions, repos_config, code_root, None)

    paths = {(t["repo_name"], t["version"]): t["repo_path"] for t in tasks}

    # plain string → one task per configured version
    assert (code_root / "oca" / "17.0" / "server-tools") == paths[("server-tools", "17.0")]
    assert (code_root / "oca" / "18.0" / "server-tools") == paths[("server-tools", "18.0")]
    # inline branch override → only the specified branches, no version loop
    assert ("oca-port", "17.0") not in paths
    assert ("oca-port", "18.0") not in paths
    assert (code_root / "oca" / "main" / "oca-port") == paths[("oca-port", "main")]
    # multiple explicit branches
    assert (code_root / "oca" / "17.0" / "oca-custom") == paths[("oca-custom", "17.0")]
    assert (code_root / "oca" / "18.0" / "oca-custom") == paths[("oca-custom", "18.0")]
    assert len(tasks) == 5
