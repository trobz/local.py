import json
import logging
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import typer
from rich.progress import Progress, TaskID

from .concurrency import TaskResult, run_tasks
from .exceptions import (
    DownloadError,
    ExecutableNotFoundError,
    PackageInstallError,
    ScriptExecutionError,
)
from .utils import (
    ARCH_PACKAGES,
    GITHUB_LATEST,
    MACOS_PACKAGES,
    UBUNTU_PACKAGES,
    get_os_info,
    get_uv_path,
)

logger = logging.getLogger(__name__)


def _get_executable_path(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise ExecutableNotFoundError(name)
    return path


def _get_download_command(url: str, output_path: str) -> list[str]:
    wget_path = shutil.which("wget")
    if wget_path:
        return [wget_path, "-q", "-O", output_path, url]

    curl_path = shutil.which("curl")
    if curl_path:
        return [curl_path, "-fsSL", "-o", output_path, url]

    raise ExecutableNotFoundError("wget/curl")


def _execute_script(script_path: Path, script_name: str) -> None:
    """Execute a shell script using full path to sh."""
    sh_path = _get_executable_path("sh")

    subprocess.run(  # noqa: S603
        [sh_path, str(script_path)],
        check=True,
        capture_output=True,
        text=True,
    )


def _install_script(progress: Progress, task_id: TaskID, script: dict, temp_dir: str):
    url = script["url"]
    script_name = script.get("name") or url

    # === Step 1: Download ===
    progress.update(task_id, description=f"Downloading {script_name}...", total=100, completed=0)

    url_filename = url.split("/")[-1].split("?")[0]
    download_path = Path(temp_dir) / url_filename

    download_cmd = _get_download_command(url, str(download_path))

    try:
        subprocess.run(download_cmd, check=True, capture_output=True, text=True)  # noqa: S603
    except subprocess.CalledProcessError as e:
        progress.update(task_id, description=f"[red]✗ Download failed: {script_name}")
        raise DownloadError(url, e.stderr) from e

    # === Step 2: Execute ===
    progress.update(task_id, description=f"Executing {script_name}...", completed=50)

    try:
        _execute_script(download_path, script_name)
    except subprocess.CalledProcessError as e:
        progress.update(task_id, description=f"[red]✗ Script execution failed: {script_name}")
        raise ScriptExecutionError(script_name, e.stderr) from e

    progress.update(task_id, description=f"✓ {script_name} executed.", completed=100)


def install_scripts(scripts: list[dict], dry_run: bool = False) -> list:
    """Download and execute scripts.

    Args:
        scripts: List of script dicts with keys:
            - url: HTTPS URL to download
            - name: Optional display name
        dry_run: If True, only show what would be installed

    """
    if not scripts:
        return []

    if dry_run:
        typer.echo("\n[Scripts - would be downloaded and executed]")
        for script in scripts:
            script_name = script["name"] if script.get("name") else script["url"]
            typer.echo(f"  - {script_name}")
        return []

    typer.secho("\n--- Installing Scripts ---", fg=typer.colors.BLUE, bold=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        tasks = []
        for script in scripts:
            script_name = script.get("name") or script["url"]
            tasks.append({
                "name": script_name,
                "func": _install_script,
                "args": {"script": script, "temp_dir": temp_dir},
            })

        return run_tasks(tasks)


def _get_package_manager_config(system: str, distro: str) -> tuple[list[str], list[str]] | None:
    """Get package manager command and default packages for the OS.

    Default package lists (MACOS_PACKAGES, UBUNTU_PACKAGES, ARCH_PACKAGES)
    include postgresql. On Debian/Ubuntu, setup_postgresql_repo() must run
    first to add the PGDG repo, otherwise apt installs the older distro version.

    Returns:
        Tuple of (command_prefix, default_packages) or None if unsupported.

    """
    if system == "Darwin":
        if not shutil.which("brew"):
            return None
        return ["brew", "install"], MACOS_PACKAGES

    if system == "Linux":
        if distro == "arch":
            return ["sudo", "pacman", "-S", "--noconfirm", "--needed"], ARCH_PACKAGES
        if distro == "ubuntu":
            return ["sudo", "apt-get", "install", "-y"], UBUNTU_PACKAGES

    return None


def _run_package_install(cmd: list[str], packages: list[str]) -> bool:
    full_cmd = cmd + packages
    try:
        subprocess.run(full_cmd, check=True, text=True)  # noqa: S603
    except subprocess.CalledProcessError as e:
        typer.secho(f"Error installing packages: {e}", fg=typer.colors.RED)
        return False
    return True


def install_system_packages(packages: list[str], dry_run: bool = False, install_defaults: bool = True) -> bool:
    os_info = get_os_info()
    system = os_info["system"]
    distro = os_info["distro"]

    config = _get_package_manager_config(system, distro)

    if config is None:
        if system == "Darwin":
            typer.secho("Error: Homebrew is not installed. Please install it first.", fg=typer.colors.RED)
        elif system == "Linux":
            typer.secho(f"Error: Unsupported Linux distribution: {distro}", fg=typer.colors.RED)
        else:
            typer.secho(f"Error: Unsupported operating system: {system}", fg=typer.colors.RED)
        return False

    cmd, default_packages = config

    all_packages = list(dict.fromkeys((default_packages if install_defaults else []) + packages))
    if not all_packages:
        return True

    if dry_run:
        typer.echo(f"\n[System packages - would be installed via {cmd[0]}]")
        for pkg in all_packages:
            source = "[default]" if pkg in default_packages else "[config]"
            typer.echo(f"  - {pkg} {source}")
        return True

    typer.secho("\n--- Installing System Packages ---", fg=typer.colors.BLUE, bold=True)
    typer.echo(f"Package manager: {cmd[0]}")
    typer.echo(f"Packages: {', '.join(all_packages)}")

    if _run_package_install(cmd, all_packages):
        typer.secho("✓ System packages installed successfully.", fg=typer.colors.GREEN)
        return True
    return False


def setup_postgresql_repo() -> bool:
    """Setup official PGDG APT repository for Debian/Ubuntu.

    On Debian/Ubuntu, the default distro repos ship older PostgreSQL versions.
    This adds the official PGDG repo so `apt-get install postgresql` pulls
    the latest version. Must run before install_system_packages().

    macOS/Arch: No-op — Homebrew and pacman already provide latest PostgreSQL,
    so the package lists in _get_package_manager_config() are sufficient.

    Idempotent: Skips if keyring already exists.

    Returns:
        True on success or if already configured (never fails the pipeline)

    """
    os_info = get_os_info()
    system = os_info["system"]
    distro = os_info["distro"]

    # macOS/Arch: no separate repo setup needed — brew/pacman handle it
    if system == "Darwin" or distro not in ["debian", "ubuntu"]:
        logger.debug(f"Skipping PostgreSQL repo setup (system: {system}, distro: {distro})")
        return True

    # Idempotent check: skip if PGDG keyring already installed
    keyring_path = Path("/usr/share/keyrings/postgresql-keyring.gpg")
    if keyring_path.exists():
        typer.echo("✓ PostgreSQL APT repository already configured")
        return True

    typer.secho("\n--- Setting up PostgreSQL APT Repository ---", fg=typer.colors.BLUE, bold=True)

    try:
        # Get distribution codename (e.g. "jammy", "bookworm")
        lsb_release_path = shutil.which("lsb_release")
        if not lsb_release_path:
            typer.secho("Warning: lsb_release not found, skipping PostgreSQL repo setup", fg=typer.colors.YELLOW)
            return True

        result = subprocess.run([lsb_release_path, "-cs"], check=True, capture_output=True, text=True)  # noqa: S603
        codename = result.stdout.strip()

        curl_path = shutil.which("curl")
        if not curl_path:
            typer.secho("Warning: curl not found, skipping PostgreSQL repo setup", fg=typer.colors.YELLOW)
            return True

        gpg_path = shutil.which("gpg")
        if not gpg_path:
            typer.secho("Warning: gpg not found, skipping PostgreSQL repo setup", fg=typer.colors.YELLOW)
            return True

        # Download and import the official PGDG GPG key
        typer.echo("Downloading PostgreSQL GPG key...")
        download_result = subprocess.run(  # noqa: S603
            [curl_path, "-fsSL", "https://www.postgresql.org/media/keys/ACCC4CF8.asc"],
            check=True,
            capture_output=True,
            text=True,
        )

        subprocess.run(  # noqa: S603
            ["sudo", gpg_path, "--dearmor", "-o", str(keyring_path)],  # noqa: S607
            input=download_result.stdout,
            check=True,
            text=True,
        )

        # Add PGDG APT source list
        typer.echo("Adding PostgreSQL APT repository...")
        repo_line = (
            f"deb [arch=amd64 signed-by={keyring_path}] https://apt.postgresql.org/pub/repos/apt {codename}-pgdg main"
        )

        tee_path = shutil.which("tee")
        if not tee_path:
            typer.secho("Warning: tee not found, skipping PostgreSQL repo setup", fg=typer.colors.YELLOW)
            return True

        subprocess.run(  # noqa: S603
            ["sudo", tee_path, "/etc/apt/sources.list.d/pgdg.list"],  # noqa: S607
            input=repo_line,
            check=True,
            capture_output=True,
            text=True,
        )

        # Refresh package index to include PGDG packages
        typer.echo("Updating package list...")
        subprocess.run(["sudo", "apt-get", "update"], check=True, capture_output=True)  # noqa: S607

        typer.secho("✓ PostgreSQL APT repository configured successfully", fg=typer.colors.GREEN)

    except subprocess.CalledProcessError as e:
        typer.secho(
            f"Warning: Failed to setup PostgreSQL repository: {e}\n"
            "You may need to configure it manually if you need PostgreSQL.",
            fg=typer.colors.YELLOW,
        )
    except Exception as e:
        typer.secho(f"Warning: Unexpected error during PostgreSQL repo setup: {e}", fg=typer.colors.YELLOW)

    return True  # Always succeeds — never fails the install-tools pipeline


def _install_npm_package(progress: Progress, task_id: TaskID, package: str, npm_path: str):
    progress.update(task_id, description=f"Installing {package}...", total=100, completed=0)

    try:
        subprocess.run(  # noqa: S603
            [npm_path, "install", "-g", package],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        progress.update(task_id, description=f"[red]✗ Failed to install {package}")
        raise PackageInstallError(package, e.stderr) from e

    progress.update(task_id, description=f"✓ {package} installed.", completed=100)


def install_npm_packages(packages: list[str], dry_run: bool = False) -> list:
    if not packages:
        return []

    npm_path = shutil.which("npm")
    if not npm_path:
        typer.secho(
            "Error: npm is not installed. Please install Node.js first.",
            fg=typer.colors.RED,
        )
        return [TaskResult(name="npm-check", success=False, message="npm is not installed")]

    if dry_run:
        typer.echo("\n[NPM packages - would be installed globally via npm]")
        for pkg in packages:
            typer.echo(f"  - {pkg}")
        return []

    typer.secho("\n--- Installing NPM Packages ---", fg=typer.colors.BLUE, bold=True)

    tasks = []
    for package in packages:
        tasks.append({
            "name": package,
            "func": _install_npm_package,
            "args": {"package": package, "npm_path": npm_path},
        })

    return run_tasks(tasks)


def _install_uv_tool(progress: Progress, task_id: TaskID, tool: str, uv_path: str):
    progress.update(task_id, description=f"Installing {tool}...", total=100, completed=0)

    try:
        subprocess.run(  # noqa: S603
            [uv_path, "tool", "install", "--", tool],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        progress.update(task_id, description=f"[red]✗ Failed to install {tool}")
        raise PackageInstallError(tool, e.stderr) from e

    progress.update(task_id, description=f"✓ {tool} installed.", completed=100)


def install_uv_tools(tools: list[str], dry_run: bool = False) -> list:
    if not tools:
        return []

    if dry_run:
        typer.echo("\n[UV tools - would be installed via uv tool install]")
        for tool in tools:
            typer.echo(f"  - {tool}")
        return []

    typer.secho("\n--- Installing UV Tools ---", fg=typer.colors.BLUE, bold=True)

    uv_path = get_uv_path()

    tasks = []
    for tool in tools:
        tasks.append({
            "name": tool,
            "func": _install_uv_tool,
            "args": {"tool": tool, "uv_path": uv_path},
        })

    return run_tasks(tasks)


# --- GitHub tool helpers ---

_SYSTEM_KEYWORDS = {
    "linux": ["linux"],
    "darwin": ["darwin", "macos", "osx"],
}

_ARCH_KEYWORDS = {
    "x86_64": ["x86_64", "amd64"],
    "aarch64": ["aarch64", "arm64"],
    "arm64": ["arm64", "aarch64"],
}


def _parse_github_owner_repo(repo_url: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL."""
    parts = repo_url.removeprefix("https://github.com/").split("/")
    return parts[0], parts[1]


def _fetch_latest_release_tag(owner: str, repo: str) -> str:
    """Return the tag name of the latest GitHub release."""
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    req = urllib.request.Request(  # noqa: S310
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "trobz-local"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            data = json.loads(resp.read())
        return data["tag_name"]
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        raise DownloadError(url, str(e)) from e


def _find_matching_asset(assets: list[dict], system: str, machine: str) -> dict | None:
    """Find a release asset matching the current OS and architecture."""
    sys_keywords = _SYSTEM_KEYWORDS.get(system, [system])
    arch_keywords = _ARCH_KEYWORDS.get(machine, [machine])

    for asset in assets:
        name = asset["name"].lower()
        if any(k in name for k in sys_keywords) and any(k in name for k in arch_keywords):
            return asset
    return None


_TEXT_EXTENSIONS = {".md", ".txt", ".rst", ".html", ".json", ".yaml", ".yml", ".xml", ".toml", ".ini", ".cfg"}
_TEXT_FILENAMES = {"LICENSE", "README", "CHANGELOG", "NOTICE", "AUTHORS", "CONTRIBUTING", "INSTALL", "COPYRIGHT"}


def _find_binary_member(members: list[tuple[str, int]], tool_name: str) -> str | None:
    """Find the best matching binary in a list of (archive_path, size) members.

    Priority:
    1. Exact basename match for tool_name
    2. Largest file that has no text extension and no known text filename
    """
    for member_path, _ in members:
        if Path(member_path).name == tool_name:
            return member_path

    candidates = [
        (size, member_path)
        for member_path, size in members
        if Path(member_path).suffix not in _TEXT_EXTENSIONS
        and Path(member_path).name not in _TEXT_FILENAMES
        and not member_path.endswith("/")
    ]
    if candidates:
        return max(candidates)[1]  # largest file wins
    return None


def _install_github_binary(
    progress: Progress, task_id: TaskID, owner: str, repo: str, version: str, name: str, temp_dir: str
):
    """Download and install a binary asset from a GitHub release."""
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{version}"
    req = urllib.request.Request(  # noqa: S310
        api_url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "trobz-local"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            release_data = json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        raise DownloadError(api_url, str(e)) from e

    assets = release_data.get("assets", [])
    if not assets:
        raise DownloadError(api_url, "No release assets found")

    system = platform.system().lower()
    machine = platform.machine().lower()
    asset = _find_matching_asset(assets, system, machine)
    if asset is None:
        available = [a["name"] for a in assets]
        raise DownloadError(api_url, f"No asset matched {system}/{machine}. Available: {available}")

    download_url = asset["browser_download_url"]
    asset_name = asset["name"]
    download_path = Path(temp_dir) / asset_name

    progress.update(task_id, description=f"Downloading {name} {version}...", completed=30)
    download_cmd = _get_download_command(download_url, str(download_path))
    try:
        subprocess.run(download_cmd, check=True, capture_output=True, text=True)  # noqa: S603
    except subprocess.CalledProcessError as e:
        raise DownloadError(download_url, e.stderr) from e

    progress.update(task_id, description=f"Installing {name}...", completed=70)
    install_dir = Path.home() / ".local" / "bin"
    install_dir.mkdir(parents=True, exist_ok=True)
    install_path = install_dir / name

    if asset_name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(download_path) as tar:
            members = [(m.name, m.size) for m in tar.getmembers() if m.isfile()]
            member_name = _find_binary_member(members, name)
            if member_name:
                f = tar.extractfile(tar.getmember(member_name))
                if f:
                    install_path.write_bytes(f.read())
    elif asset_name.endswith(".zip"):
        with zipfile.ZipFile(download_path) as zf:
            members = [(i.filename, i.file_size) for i in zf.infolist() if not i.is_dir()]
            member_name = _find_binary_member(members, name)
            if member_name:
                install_path.write_bytes(zf.read(member_name))
    else:
        shutil.copy2(str(download_path), str(install_path))

    install_path.chmod(0o755)
    progress.update(task_id, description=f"✓ {name} installed to {install_path}.", completed=100)


def _install_github_tool(progress: Progress, task_id: TaskID, tool: dict, temp_dir: str):
    name = tool["name"]
    repo_url = tool["repo"]
    version = tool["version"]
    script = tool.get("script")

    progress.update(task_id, description=f"Installing {name}...", total=100, completed=0)

    owner, repo = _parse_github_owner_repo(repo_url)

    if version == GITHUB_LATEST:
        progress.update(task_id, description=f"Fetching latest release for {name}...")
        version = _fetch_latest_release_tag(owner, repo)

    if script:
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{version}/{script}"
        _install_script(progress, task_id, {"url": raw_url, "name": name}, temp_dir)
    else:
        _install_github_binary(progress, task_id, owner, repo, version, name, temp_dir)


def install_github_tools(tools: list[dict], dry_run: bool = False) -> list:
    """Install tools from GitHub releases (via install script or binary asset).

    Args:
        tools: List of tool dicts with keys: name, repo, version, script (optional).
        dry_run: If True, only show what would be installed.

    """
    if not tools:
        return []

    if dry_run:
        typer.echo("\n[GitHub tools - would be installed from GitHub releases]")
        for tool in tools:
            version_label = "latest release" if tool["version"] == GITHUB_LATEST else tool["version"]
            method = f"script: {tool['script']}" if tool.get("script") else "binary asset"
            typer.echo(f"  - {tool['name']} ({tool['repo']}, {version_label}, {method})")
        return []

    typer.secho("\n--- Installing GitHub Tools ---", fg=typer.colors.BLUE, bold=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        tasks = []
        for tool in tools:
            tasks.append({
                "name": tool["name"],
                "func": _install_github_tool,
                "args": {"tool": tool, "temp_dir": temp_dir},
            })
        return run_tasks(tasks)
