import subprocess
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from trobz_local.main import app
from trobz_local.utils import ARCH_PACKAGES, MACOS_PACKAGES, UBUNTU_PACKAGES

runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_typer_confirm():
    with patch("typer.confirm", return_value=True) as mock_tc:
        yield mock_tc


def test_install_packages_unsupported_os():
    with (
        patch("trobz_local.main.get_os_info", return_value={"system": "Windows", "distro": "unknown"}),
    ):
        result = runner.invoke(app, ["install-packages"])
        assert result.exit_code == 1
        assert "Unsupported operating system" in result.stdout


def test_install_packages_macos_brew_missing():
    with (
        patch("trobz_local.main.get_os_info", return_value={"system": "Darwin", "distro": "macos"}),
        patch("shutil.which", return_value=None),
    ):
        result = runner.invoke(app, ["install-packages"])
        assert result.exit_code == 1
        assert "Homebrew is not installed" in result.stdout


def test_install_packages_macos_success():
    with (
        patch("trobz_local.main.get_os_info", return_value={"system": "Darwin", "distro": "macos"}),
        patch("shutil.which", return_value="/usr/local/bin/brew"),
        patch("trobz_local.main.subprocess.run") as mock_run,
    ):
        result = runner.invoke(app, ["install-packages"])
        assert result.exit_code == 0
        mock_run.assert_called_with(
            ["brew", "install"] + MACOS_PACKAGES,
            check=True,
            text=True,
        )


def test_install_packages_arch_success():
    with (
        patch("trobz_local.main.get_os_info", return_value={"system": "Linux", "distro": "arch"}),
        patch("trobz_local.main.subprocess.run") as mock_run,
    ):
        result = runner.invoke(app, ["install-packages"])
        assert result.exit_code == 0
        mock_run.assert_called_with(
            ["sudo", "pacman", "-S", "--noconfirm", "--needed"] + ARCH_PACKAGES,
            check=True,
            text=True,
        )


def test_install_packages_ubuntu_success():
    with (
        patch("trobz_local.main.get_os_info", return_value={"system": "Linux", "distro": "ubuntu"}),
        patch("trobz_local.main.subprocess.run") as mock_run,
    ):
        result = runner.invoke(app, ["install-packages"])
        assert result.exit_code == 0
        mock_run.assert_called_with(
            ["sudo", "apt-get", "install", "-y"] + UBUNTU_PACKAGES,
            check=True,
            text=True,
        )


def test_install_packages_subprocess_error():
    with patch("trobz_local.main.get_os_info", return_value={"system": "Linux", "distro": "arch"}):
        error = subprocess.CalledProcessError(1, ["cmd"], stderr="Installation failed")
        with patch("trobz_local.main.subprocess.run", side_effect=error):
            result = runner.invoke(app, ["install-packages"])
            assert result.exit_code == 0
            assert "Error installing packages" in result.stdout
            assert "Installation failed" in result.stdout
