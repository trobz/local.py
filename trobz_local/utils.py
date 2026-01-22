import os
import platform
import re
import shutil
from pathlib import Path

import git
import tomli
import typer
from pydantic import BaseModel, Field, ValidationError, field_validator
from rich import print as rprint
from rich.progress import (
    Progress,
    TaskID,
)

TOOL_NAME_REGEX = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._\-\[\]@=<>!,]*$")
VERSION_REGEX = re.compile(r"^\d+\.\d+$")

ARCH_PACKAGES = [
    "gcc",
    "postgresql",
    "postgresql-libs",
    "libxml2",
    "libxslt",
    "libjpeg",
    "libsass",
    "base-devel",
    "git",
]

UBUNTU_PACKAGES = [
    "git",
    "gcc",
    "libsasl2-dev",
    "libldap2-dev",
    "libssl-dev",
    "libffi-dev",
    "libxml2-dev",
    "libxslt1-dev",
    "libjpeg-dev",
    "libpq-dev",
    "libsass-dev",
    "postgresql",
    "postgresql-client",
    "postgresql-contrib",
]

MACOS_PACKAGES = [
    "git",
    "postgresql",
    "node",
]


class InvalidRepoNameError(ValueError):
    def __init__(self, name: str):
        super().__init__(f"Invalid repo name: {name}")


class InvalidVersionError(ValueError):
    def __init__(self, version: str):
        super().__init__(f"Invalid Odoo version format: {version}")


class InvalidToolNameError(ValueError):
    def __init__(self, tool: str):
        super().__init__(f"Invalid tool name: {tool}")


class InvalidScriptUrlError(ValueError):
    def __init__(self, url: str):
        super().__init__(f"Script URL must use HTTPS for security: {url}")


class InvalidNpmPackageError(ValueError):
    def __init__(self, pkg: str):
        super().__init__(f"Invalid npm package name: {pkg}")


class RepoConfig(BaseModel):
    odoo: list[str] = []
    oca: list[str] = []

    @field_validator("*")
    @classmethod
    def validate_repo_names(cls, v: list[str]):
        for name in v:
            if not re.match(r"^[a-zA-Z0-9._-]+$", name):
                raise InvalidRepoNameError(name)
        return v


class ScriptItem(BaseModel):
    """Configuration for a script to download and execute."""

    url: str
    install_script: str = "install.sh"
    name: str | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str):
        if not v.startswith("https://"):
            raise InvalidScriptUrlError(v)
        return v


class ToolsConfig(BaseModel):
    """Configuration for tools to install."""

    uv: list[str] = Field(default_factory=list)
    npm: list[str] = Field(default_factory=list)
    script: list[ScriptItem] = Field(default_factory=list)
    system_packages: list[str] = Field(default_factory=list)

    @field_validator("uv")
    @classmethod
    def validate_uv_tools(cls, v: list[str]):
        for tool in v:
            if not TOOL_NAME_REGEX.match(tool):
                raise InvalidToolNameError(tool)
        return v

    @field_validator("npm")
    @classmethod
    def validate_npm_packages(cls, v: list[str]):
        for pkg in v:
            if not re.match(r"^(@[a-z0-9-~][a-z0-9-._~]*/)?[a-z0-9-~][a-z0-9-._~]*$", pkg):
                raise InvalidNpmPackageError(pkg)
        return v


class ConfigModel(BaseModel):
    versions: list[str] = Field(default_factory=list)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    repos: RepoConfig = Field(default_factory=RepoConfig)

    @field_validator("versions")
    @classmethod
    def validate_versions(cls, v: list[str]):
        for version in v:
            if not VERSION_REGEX.match(version):
                raise InvalidVersionError(version)
        return v


def get_code_root() -> Path:
    """Get the code root directory from TLC_CODE_DIR env var or default to ~/code."""
    env_code_dir = os.environ.get("TLC_CODE_DIR")
    if env_code_dir:
        return Path(os.path.expanduser(env_code_dir))
    return Path.home() / "code"


def get_uv_path():
    uv_path = shutil.which("uv")
    if not uv_path:
        typer.secho("Error: uv is not installed. Please install uv first.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    return uv_path


def show_config_instructions():
    content = """versions = ["14.0", "15.0", "16.0", "17.0", "18.0"]

[tools]
uv = [
    "odoo-venv",
    "odoo-addons-path",
    "pre-commit",
]

npm = [
    "prettier",
]

[[tools.script]]
name = "uv"
url = "https://astral.sh/uv/install.sh"

[[tools.script]]
name = "nvm"
url = "https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh"

system_packages = [
    "pnpm",
]

[repos]
odoo = [
    "odoo",
    "enterprise",
]

oca = [
    "server-tools",
    "server-ux",
]
"""
    typer.secho("Config file not found.", fg=typer.colors.YELLOW)
    code_root = get_code_root()
    typer.echo(f"Please create {code_root}/config.toml with content like this:")
    typer.echo(content)


def get_config():
    """Loads and validates configuration from code_dir/config.toml."""
    config_path = get_code_root() / "config.toml"
    if not config_path.exists():
        show_config_instructions()
        raise typer.Exit(code=1)

    try:
        with open(config_path, "rb") as f:
            raw_config = tomli.load(f)
    except tomli.TOMLDecodeError as e:
        typer.secho(f"Error: Invalid TOML in {config_path}", fg=typer.colors.RED)
        typer.echo(str(e))
        raise typer.Exit(code=1) from e

    try:
        validated_config = ConfigModel(**raw_config)
    except ValidationError as e:
        for error in e.errors():
            typer.secho(f"{error['msg']}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None

    return validated_config.model_dump()


# NOTE: there are actually 2 phases when git.Repo.clone_from
# fetching objects + writing files
class GitProgress(git.remote.RemoteProgress):
    def __init__(self, progress: Progress, task_id: TaskID, description_prefix: str):
        super().__init__()
        self.progress = progress
        self.task_id = task_id
        self.description_prefix = description_prefix
        self.progress.update(self.task_id, description=self.description_prefix)

    def update(self, op_code, cur_count, max_count=None, message=""):
        self.progress.update(
            self.task_id,
            total=max_count,
            completed=cur_count,
        )


def confirm_step(ctx: typer.Context, message: str, command: str):
    """
    If in newcomer mode, prints a help message and asks for confirmation to proceed.
    """
    if ctx.obj.get("newcomer", False):
        typer.secho(f"About to run: {command}", fg=typer.colors.BLUE)
        rprint(message)
        if not typer.confirm("Do you want to proceed?"):
            raise typer.Abort()


def get_os_info() -> dict:
    system = platform.system()
    info = {"system": system, "distro": "unknown"}

    if system == "Darwin":
        info["distro"] = "macos"
    elif system == "Linux":
        try:
            os_release = platform.freedesktop_os_release()
            info["distro"] = os_release.get("ID", "unknown")
        except (AttributeError, OSError):
            pass

    return info
