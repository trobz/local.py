import subprocess
import urllib.request
from enum import Enum
from importlib.resources import files
from pathlib import Path
from typing import Annotated

import git
import typer
from rich import print as rprint
from rich.console import Console
from rich.progress import Progress, TaskID
from rich.table import Table
from rich.tree import Tree

from .concurrency import TaskResult, run_tasks
from .doctor import CheckStatus, run_doctor
from .installers import (
    install_npm_packages,
    install_scripts,
    install_system_packages,
    install_uv_tools,
    setup_postgresql_repo,
)
from .postgres import (
    check_postgres_running,
    check_user_exists,
    create_user,
    verify_connection,
)
from .utils import (
    GitProgress,
    confirm_step,
    get_code_root,
    get_config,
    get_os_info,
    get_uv_path,
)

app = typer.Typer()

ODOO_URLS = {
    "odoo": "git@github.com:odoo/odoo.git",
    "enterprise": "git@github.com:odoo/enterprise.git",
}


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    newcomer: bool = typer.Option(
        True,
        help="Enable newcomer mode with confirmations and help.",
        envvar="NEWCOMER_MODE",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip all confirmations (non-interactive mode).",
    ),
):
    """
    Hi, I'm a CLI to help you setup and manage your local environment for Odoo development.
    """
    ctx.ensure_object(dict)
    ctx.obj["newcomer"] = newcomer and not yes
    if ctx.invoked_subcommand is None:
        _run_init(ctx)


@app.command()
def init(ctx: typer.Context):
    _run_init(ctx)


def _run_init(ctx: typer.Context):
    code_root = get_code_root()
    confirm_step(
        ctx,
        f"This command will create the basic directory structure for your local "
        f"development environment inside '{code_root}'",
        "init",
    )
    config = get_config()
    # Hardcoded defaults
    dirs = [
        "venvs",
        "oca",
        "odoo",
        "odoo/odoo",
    ]
    # Additional directories from config
    dirs.extend(config.get("init_dirs", []))
    for d in dirs:
        (code_root / d).mkdir(parents=True, exist_ok=True)

    odoo_versions = config.get("versions")
    if not odoo_versions:
        typer.echo("versions not found in config file.")
        raise typer.Exit(code=1)

    for version in odoo_versions:
        (code_root / "oca" / version).mkdir(parents=True, exist_ok=True)

    root_path = code_root
    typer.secho("Required directories are created successfully.", fg=typer.colors.GREEN)
    tree = Tree(f"[bold yellow]{root_path}[/bold yellow]")

    tree.add("venvs [dim]# Virtual environments[/dim]")

    oca_tree = tree.add("oca [dim]# OCA repositories[/dim]")
    for version in odoo_versions:
        oca_tree.add(f"{version}")

    odoo_tree = tree.add("odoo [dim]# Odoo source code[/dim]")
    community = odoo_tree.add("odoo [dim]# Odoo Community[/dim]")
    for version in odoo_versions:
        community.add(f"{version}")

    # Show additional directories from config
    extra_dirs = config.get("init_dirs", [])
    for d in extra_dirs:
        tree.add(f"{d}")
    rprint(tree)


@app.command()
def pull_repos(  # noqa: C901
    ctx: typer.Context,
    repo_filter: Annotated[
        list[str] | None,
        typer.Option(
            "--filter",
            "-f",
            help="Filter by repo name. Can be used multiple times.",
        ),
    ] = None,
    dry_run: bool = typer.Option(False, "--dry-run", help="Prints actions without running."),
):
    """
    Pull/clone Odoo and OCA repos based on config
    """
    config = get_config()
    odoo_versions = config.get("versions", [])
    repos_config = config.get("repos", {})
    code_root = get_code_root()

    repo_infos_for_tasks = _get_tasks(odoo_versions, repos_config, code_root, repo_filter)

    if not repo_infos_for_tasks:
        return

    # Group tasks by repo_name
    tasks_by_repo = {}
    for task in repo_infos_for_tasks:
        tasks_by_repo.setdefault(task["repo_name"], []).append(task)

    msg = "This command will clone/pull the following repositories:\n"
    for repo_name, repo_tasks in tasks_by_repo.items():
        msg += f"\n{repo_name}:\n"
        for task in repo_tasks:
            try:
                repo_path_display = f"~/{task['repo_path'].relative_to(Path.home())}"
            except ValueError:
                repo_path_display = str(task["repo_path"])

            msg += f"- {task['version']} -> {repo_path_display}\n"
    msg += "\nEnsuring your local code is up to date."

    confirm_step(
        ctx,
        msg,
        "pull-repos",
    )

    if dry_run:
        for repo_info in repo_infos_for_tasks:
            action = "Clone" if not repo_info["repo_path"].exists() else "Pull"
            typer.echo(f"- {action} {repo_info['repo_name']} (branch: {repo_info['version']})")
        return

    concurrency_tasks = []
    for repo_info in repo_infos_for_tasks:
        concurrency_tasks.append({
            "name": f"{repo_info['repo_name']} ({repo_info['version']})",
            "func": _pull_repo,
            "args": {"repo_info": repo_info},
        })

    results = run_tasks(concurrency_tasks)
    failed_tasks = [res for res in results if not res.success]
    if failed_tasks:
        typer.secho("\n--- Some repository operations failed ---", fg=typer.colors.RED)
        for res in failed_tasks:
            typer.secho(f"✗ {res.name}: {res.message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    else:
        typer.secho("\nAll repositories updated successfully.", fg=typer.colors.GREEN)


def _iter_org_entries(org_repos, odoo_versions):
    """Yield (repo_name, branch) pairs for an org's repo list.

    Plain strings use all configured versions; [name, [branch, ...]] entries
    use their explicit branch list.
    """
    for entry in org_repos:
        if isinstance(entry, str):
            for version in odoo_versions:
                yield entry, str(version)
        else:
            for branch in entry[1]:
                yield entry[0], str(branch)


def _get_tasks(odoo_versions, repos_config, code_root, repo_filter):
    tasks = []
    for version in odoo_versions:
        for repo_name in repos_config.get("odoo", []):
            if repo_name in ODOO_URLS and (not repo_filter or repo_name in repo_filter):
                tasks.append({
                    "repo_name": repo_name,
                    "repo_path": code_root / "odoo" / repo_name / version,
                    "repo_url": ODOO_URLS[repo_name],
                    "version": str(version),
                })
    for org, org_repos in repos_config.items():
        if org == "odoo":
            continue
        for repo_name, branch in _iter_org_entries(org_repos, odoo_versions):
            if not repo_filter or repo_name in repo_filter:
                tasks.append({
                    "repo_name": repo_name,
                    "repo_path": code_root / org / branch / repo_name,
                    "repo_url": f"git@github.com:{org}/{repo_name}.git",
                    "version": branch,
                })
    return tasks


def _pull_repo(progress: Progress, task_id: TaskID, repo_info: dict):
    repo_name = repo_info["repo_name"]
    repo_path = repo_info["repo_path"]
    repo_url = repo_info["repo_url"]
    version = repo_info["version"]

    try:
        progress.update(task_id, description=f"Processing {repo_name} ({version})", total=100, completed=0)
        if not repo_path.exists():
            progress.update(task_id, description=f"Cloning {repo_name} ({version})")
            repo_path.parent.mkdir(parents=True, exist_ok=True)
            git.Repo.clone_from(
                repo_url,
                to_path=repo_path,
                branch=version,
                progress=GitProgress(progress, task_id, f"Cloning {repo_name} {version}"),  # ty: ignore[invalid-argument-type]
                depth=1,
            )
        else:
            progress.update(task_id, description=f"Fetching {repo_name} ({version})")
            repo = git.Repo(repo_path)
            origin = repo.remotes.origin
            origin.fetch(version)
            repo.heads[version].checkout()
            repo.git.reset("--hard", f"origin/{version}")

        progress.update(task_id, description=f"✓ {repo_name} ({version}) updated.", completed=100, total=100)

    except git.exc.InvalidGitRepositoryError as e:
        progress.update(task_id, description=f"[red]✗ Error {repo_name} ({version}): Not a git repository: {e}")
        raise
    except git.exc.GitCommandError as e:
        progress.update(task_id, description=f"[red]✗ Error {repo_name} ({version}): {e.stderr.strip()}")
        raise
    except Exception as e:
        progress.update(task_id, description=f"[red]✗ Error {repo_name} ({version}): {e}")
        raise  # to be caught by run_tasks


def _build_install_message(tools_config: dict) -> str:
    msg = "This command will install tools in the following order:\n"

    if tools_config.get("script"):
        msg += "\n[1] Scripts (download & execute):\n"
        for script in tools_config["script"]:
            name = script.get("name") if isinstance(script, dict) else getattr(script, "name", None)
            url = script["url"] if isinstance(script, dict) else script.url
            sha256 = script.get("sha256") if isinstance(script, dict) else getattr(script, "sha256", None)
            display_name = name or url
            hash_status = "✓ verified" if sha256 else "⚠ no hash"
            msg += f"  - {display_name} ({hash_status})\n"

    if tools_config.get("system_packages"):
        msg += "\n[2] System packages:\n"
        for pkg in tools_config["system_packages"]:
            msg += f"  - {pkg}\n"

    if tools_config.get("npm"):
        msg += "\n[3] NPM packages (via npm -g):\n"
        for pkg in tools_config["npm"]:
            msg += f"  - {pkg}\n"

    if tools_config.get("uv"):
        msg += "\n[4] UV tools:\n"
        for tool in tools_config["uv"]:
            msg += f"  - {tool}\n"

    return msg


def _run_installers(
    tools_config: dict, dry_run: bool, install_default_system_packages: bool = True
) -> tuple[list, bool]:
    all_results = []
    any_failed = False

    if tools_config.get("script"):
        scripts = [
            {
                "url": s["url"] if isinstance(s, dict) else s.url,
                "sha256": s.get("sha256") if isinstance(s, dict) else getattr(s, "sha256", None),
                "name": s.get("name") if isinstance(s, dict) else getattr(s, "name", None),
            }
            for s in tools_config["script"]
        ]
        results = install_scripts(scripts, dry_run)
        all_results.extend(results)
        if any(not r.success for r in results):
            any_failed = True

    # Setup PostgreSQL repository before system package installation
    if not dry_run:
        setup_postgresql_repo()

    success = install_system_packages(tools_config.get("system_packages", []), dry_run, install_default_system_packages)
    if not success:
        any_failed = True
        all_results.append(
            TaskResult(name="system-packages", success=False, message="System package installation failed")
        )

    if tools_config.get("npm"):
        results = install_npm_packages(tools_config["npm"], dry_run)
        all_results.extend(results)
        if any(not r.success for r in results):
            any_failed = True

    if tools_config.get("uv"):
        results = install_uv_tools(tools_config["uv"], dry_run)
        all_results.extend(results)
        if any(not r.success for r in results):
            any_failed = True

    return all_results, any_failed


@app.command()
def install_tools(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be installed without executing."),
    install_default_system_packages: bool = typer.Option(True, help="Install default OS system packages."),
):
    """
    Install tools using uv tool based on config.
    """
    config = get_config()
    tools_config = config.get("tools", {})

    has_any = any([
        tools_config.get("script"),
        tools_config.get("system_packages"),
        tools_config.get("npm"),
        tools_config.get("uv"),
    ])

    if not has_any:
        code_root = get_code_root()
        typer.echo(f"No tools found in config. Add tools to [tools] section in {code_root}/config.toml")
        return

    msg = _build_install_message(tools_config)
    confirm_step(ctx, msg, "install-tools")

    all_results, any_failed = _run_installers(tools_config, dry_run, install_default_system_packages)

    if not dry_run:
        if any_failed:
            failed = [r for r in all_results if not r.success]
            typer.secho("\n--- Some installations failed ---", fg=typer.colors.RED)
            for r in failed:
                typer.secho(f"✗ {r.name}: {r.message}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        else:
            typer.secho("\n✓ All tools installed successfully.", fg=typer.colors.GREEN)


@app.command()
def create_venvs(ctx: typer.Context):
    """
    Create virtual environments for Odoo versions using odoo-venv.
    """
    config = get_config()
    versions = config.get("versions", [])

    if not versions:
        typer.echo("No versions found in config.")
        return

    code_root = get_code_root()
    venv_dir_base = code_root / "venvs"

    msg = (
        "This command will create Python virtual environments for the following Odoo versions "
        "using 'odoo-venv' with the 'local' preset:\n\n"
    )
    for version in versions:
        msg += f"- {version} -> {venv_dir_base / version}\n"

    msg += "\nTo activate a virtual environment manually, run:\n"
    msg += f"[bold cyan]source {venv_dir_base / '<version>'}/bin/activate[/bold cyan]\n"

    msg += "\nFor more information, read at https://github.com/trobz/odoo-venv."

    if config.get("create_launcher", True):
        msg += "\nLauncher scripts will be created in ~/.local/bin/ (e.g. odoo-v18).\n"

    confirm_step(
        ctx,
        msg,
        "create-venvs",
    )

    uv_path = get_uv_path()
    odoo_dir_base = code_root / "odoo" / "odoo"
    create_launcher = config.get("create_launcher", True)

    concurrency_tasks = []
    for version in versions:
        concurrency_tasks.append({
            "name": f"venv-{version}",
            "func": _create_venvs,
            "args": {
                "version": version,
                "uv_path": uv_path,
                "odoo_dir_base": odoo_dir_base,
                "venv_dir_base": venv_dir_base,
                "create_launcher": create_launcher,
            },
        })
    results = run_tasks(concurrency_tasks)
    failed_tasks = [res for res in results if not res.success]
    if failed_tasks:
        typer.secho("\n--- Some virtual environment operations failed ---", fg=typer.colors.RED)
        for res in failed_tasks:
            error_message = f"✗ {res.name}: {res.message}"
            typer.secho(error_message, fg=typer.colors.RED)
        raise typer.Exit(code=1)
    else:
        typer.secho("\nAll virtual environments created successfully.", fg=typer.colors.GREEN)


def _create_venvs(
    progress: Progress,
    task_id: TaskID,
    version: str,
    uv_path: str,
    odoo_dir_base: Path,
    venv_dir_base: Path,
    create_launcher: bool = True,
):
    progress.update(task_id, description=f"Creating venv for {version}...", total=100, completed=0, start=True)
    odoo_dir = odoo_dir_base / version
    venv_dir = venv_dir_base / version

    try:
        cmd = [
            uv_path,
            "tool",
            "run",
            "odoo-venv",
            "create",
            version,
            "--odoo-dir",
            str(odoo_dir),
            "--venv-dir",
            str(venv_dir),
            "--preset",
            "local",
            "--verbose",
        ]
        if create_launcher:
            cmd.append("--create-launcher")

        subprocess.run(  # noqa: S603
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        progress.update(task_id, description=f"✓ Venv for {version} created.", completed=100)
    except subprocess.CalledProcessError as e:
        progress.update(task_id, description=f"[red]✗ Error venv {version}: {e.stderr.strip()}")
        raise
    except Exception as e:
        progress.update(task_id, description=f"[red]✗ Error venv {version}: {e}")
        raise


@app.command()
def ensure_db_user(ctx: typer.Context):
    """Ensure PostgreSQL user exists for Odoo development."""
    username = "odoo"
    password = "odoo"  # noqa: S105
    host = "localhost"

    confirm_step(
        ctx,
        "This command will verify/create PostgreSQL user 'odoo' with CREATEDB permission.\n"
        "Credentials: odoo:odoo (dev-only, never use in production)",
        "ensure-db-user",
    )

    os_info = get_os_info()
    system = os_info["system"]

    # Check PostgreSQL is running
    typer.echo("Checking PostgreSQL status...")
    if not check_postgres_running():
        typer.secho("✗ PostgreSQL is not running on localhost", fg=typer.colors.RED)
        if system == "Darwin":
            typer.echo("Try: brew services start postgresql")
        elif system == "Linux":
            typer.echo("Try: sudo systemctl start postgresql")
        raise typer.Exit(code=1)
    typer.secho("✓ PostgreSQL is running", fg=typer.colors.GREEN)

    # Check if user exists
    typer.echo(f"Checking if user '{username}' exists...")
    if check_user_exists(username, system):
        typer.secho(f"✓ User '{username}' already exists", fg=typer.colors.GREEN)
    else:
        typer.echo(f"User '{username}' not found, creating...")
        success, error_msg = create_user(username, password, system)
        if not success:
            typer.secho(f"✗ Failed to create user '{username}'", fg=typer.colors.RED)
            if system == "Linux" and "sudo" in error_msg.lower():
                typer.echo("Manual instructions:")
                typer.echo("  sudo -u postgres createuser -s odoo")
                typer.echo("  sudo -u postgres psql -c \"ALTER USER odoo WITH PASSWORD 'odoo';\"")
            else:
                typer.echo(f"Error: {error_msg}")
            raise typer.Exit(code=1)
        typer.secho(f"✓ User '{username}' created successfully", fg=typer.colors.GREEN)

    # Test connection
    typer.echo("Testing connection...")
    if not verify_connection(host, username, password):
        typer.secho("✗ Connection test failed", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.secho("✓ Connection successful", fg=typer.colors.GREEN)

    typer.echo()
    typer.secho(f"✓ PostgreSQL user '{username}' is ready for Odoo development", fg=typer.colors.GREEN)
    typer.echo()
    typer.secho("⚠️  WARNING: Using dev-only credentials (odoo:odoo). Never use in production!", fg=typer.colors.YELLOW)


_STATUS_ICONS = {
    CheckStatus.OK: "[green]OK[/green]",
    CheckStatus.WARN: "[yellow]!![/yellow]",
    CheckStatus.FAIL: "[red]FAIL[/red]",
}


@app.command()
def doctor():
    code_root = get_code_root()
    groups = run_doctor(code_root)

    console = Console()
    has_fail = False
    counts = {CheckStatus.OK: 0, CheckStatus.WARN: 0, CheckStatus.FAIL: 0}

    for group_name, results in groups.items():
        table = Table(title=group_name, show_header=True, title_style="bold cyan")
        table.add_column("Status", width=6, justify="center")
        table.add_column("Check", min_width=15)
        table.add_column("Details")

        for r in results:
            counts[r.status] += 1
            if r.status == CheckStatus.FAIL:
                has_fail = True
            table.add_row(_STATUS_ICONS[r.status], r.name, r.message)

        console.print(table)
        console.print()

    summary = (
        f"[green]{counts[CheckStatus.OK]} passed[/green], "
        f"[yellow]{counts[CheckStatus.WARN]} warnings[/yellow], "
        f"[red]{counts[CheckStatus.FAIL]} failures[/red]"
    )
    console.print(f"Summary: {summary}")

    if has_fail:
        raise typer.Exit(code=1)


ALL_REPOS_URL = "https://raw.githubusercontent.com/trobz/odoo-addons-repos/main/all_repos_all_versions.toml"

_ASSETS = files("trobz_local").joinpath("assets")


class ConfigProfile(str, Enum):
    odoo_minimal = "odoo-minimal"
    oca_contributor = "oca-contributor"


@app.command()
def generate_config(
    ctx: typer.Context,
    profile: Annotated[ConfigProfile, typer.Argument(help="Configuration profile to generate.")],
):
    """Generate a config.toml file from a predefined profile."""
    code_root = get_code_root()
    config_path = code_root / "config.toml"

    if config_path.exists() and ctx.obj.get("newcomer", True):
        typer.secho(f"Config file already exists: {config_path}", fg=typer.colors.YELLOW)
        if not typer.confirm("Overwrite?", default=False):
            raise typer.Abort()

    if profile == ConfigProfile.odoo_minimal:
        content = (_ASSETS / "odoo_minimal.toml").read_text()
    else:
        content = _build_oca_contributor_config()

    code_root.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content)
    typer.secho(f"Config written to {config_path}", fg=typer.colors.GREEN)


def _build_oca_contributor_config() -> str:
    typer.echo(f"Fetching OCA repo list from {ALL_REPOS_URL} ...")
    try:
        with urllib.request.urlopen(ALL_REPOS_URL, timeout=30) as resp:  # noqa: S310
            remote_content = resp.read().decode()
    except Exception as e:
        typer.secho(f"Failed to fetch repo list: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from e

    local_content = (_ASSETS / "oca_contributor.toml").read_text()
    return local_content + "\n" + remote_content
