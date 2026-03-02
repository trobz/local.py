import json
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import tomli
from pydantic import ValidationError

from .utils import ConfigModel


class CheckStatus(Enum):
    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    message: str
    detail: str = field(default="")


def check_config(code_root: Path) -> CheckResult:
    """Check config.toml exists, is valid TOML, and passes schema validation."""
    config_path = code_root / "config.toml"

    if not config_path.exists():
        return CheckResult(
            name="Config file",
            status=CheckStatus.WARN,
            message=f"Not found at {config_path}",
        )

    try:
        with open(config_path, "rb") as f:
            raw = tomli.load(f)
    except tomli.TOMLDecodeError as e:
        return CheckResult(
            name="Config file",
            status=CheckStatus.FAIL,
            message="Invalid TOML",
            detail=str(e),
        )

    try:
        validated = ConfigModel(**raw)
    except ValidationError as e:
        errors = "; ".join(err["msg"] for err in e.errors())
        return CheckResult(
            name="Config file",
            status=CheckStatus.FAIL,
            message="Schema validation failed",
            detail=errors,
        )

    version_count = len(validated.versions)
    return CheckResult(
        name="Config file",
        status=CheckStatus.OK,
        message=f"Valid — {version_count} version(s) defined",
    )


def check_github_ssh() -> CheckResult:
    """Check GitHub SSH authentication."""
    ssh_path = shutil.which("ssh")
    if not ssh_path:
        return CheckResult(
            name="GitHub SSH",
            status=CheckStatus.FAIL,
            message="ssh binary not found",
        )

    try:
        result = subprocess.run(  # noqa: S603
            [
                ssh_path,
                "-T",
                "git@github.com",
                "-o",
                "ConnectTimeout=5",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "BatchMode=yes",
            ],
            capture_output=True,
            text=True,
            timeout=8,
        )
        stderr = result.stderr or ""
        if "successfully authenticated" in stderr.lower():
            return CheckResult(
                name="GitHub SSH",
                status=CheckStatus.OK,
                message="Authenticated",
            )
        return CheckResult(
            name="GitHub SSH",
            status=CheckStatus.FAIL,
            message="Authentication failed",
            detail=stderr.strip(),
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name="GitHub SSH",
            status=CheckStatus.WARN,
            message="Timeout — could not reach github.com",
        )
    except Exception as e:
        return CheckResult(
            name="GitHub SSH",
            status=CheckStatus.FAIL,
            message="Connection error",
            detail=str(e),
        )


def _check_uv_tools(tools: list[str]) -> list[CheckResult]:
    """Check which uv tools are installed."""
    uv_path = shutil.which("uv")
    if not uv_path:
        return [CheckResult(name=f"uv: {t}", status=CheckStatus.WARN, message="uv not found — skipping") for t in tools]

    try:
        result = subprocess.run(  # noqa: S603
            [uv_path, "tool", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout or ""
    except Exception:
        return [
            CheckResult(name=f"uv: {t}", status=CheckStatus.WARN, message="Could not run uv tool list") for t in tools
        ]

    # Parse lines like "ruff v0.11.5" or "ruff 0.11.5"
    installed: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            tool_name = parts[0]
            version = parts[1].lstrip("v")
            installed[tool_name] = version

    results = []
    for tool in tools:
        # Tool name may include extras like "ruff[extra]" — use base name for lookup
        base_name = tool.split("[")[0]
        if base_name in installed:
            results.append(
                CheckResult(
                    name=f"uv: {tool}",
                    status=CheckStatus.OK,
                    message=f"v{installed[base_name]}",
                )
            )
        else:
            results.append(
                CheckResult(
                    name=f"uv: {tool}",
                    status=CheckStatus.WARN,
                    message="Not installed",
                )
            )
    return results


def _check_npm_packages(packages: list[str]) -> list[CheckResult]:
    """Check which global npm packages are installed."""
    npm_path = shutil.which("npm")
    if not npm_path:
        return [
            CheckResult(name=f"npm: {p}", status=CheckStatus.WARN, message="npm not found — skipping") for p in packages
        ]

    try:
        result = subprocess.run(  # noqa: S603
            [npm_path, "list", "-g", "--depth=0", "--json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        data = json.loads(result.stdout or "{}")
        deps = data.get("dependencies", {})
    except Exception:
        return [
            CheckResult(name=f"npm: {p}", status=CheckStatus.WARN, message="Could not run npm list") for p in packages
        ]

    results = []
    for pkg in packages:
        if pkg in deps:
            version = deps[pkg].get("version", "?")
            results.append(
                CheckResult(
                    name=f"npm: {pkg}",
                    status=CheckStatus.OK,
                    message=f"{version})",
                )
            )
        else:
            results.append(
                CheckResult(
                    name=f"npm: {pkg}",
                    status=CheckStatus.WARN,
                    message="Not installed",
                )
            )
    return results


# System-level binaries that should always be checked
SYSTEM_TOOLS = ["uv", "gh", "git", "npm", "psql"]


def check_system_tools() -> list[CheckResult]:
    """Check presence of required system-level binaries."""
    results: list[CheckResult] = []
    for tool in SYSTEM_TOOLS:
        path = shutil.which(tool)
        if path:
            # Get version where possible
            version = _get_tool_version(path, tool)
            msg = f"{version}" if version else f"Found at {path}"
            results.append(CheckResult(name=tool, status=CheckStatus.OK, message=msg))
        else:
            results.append(CheckResult(name=tool, status=CheckStatus.WARN, message="Not found"))
    return results


def _get_tool_version(path: str, tool: str) -> str:
    """Try to get a tool's version string. Returns empty string on failure."""
    try:
        result = subprocess.run(  # noqa: S603
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = (result.stdout or result.stderr or "").strip()
        # Take first line only
        return output.splitlines()[0] if output else ""
    except Exception:
        return ""


def check_tool_versions(tools_config: dict) -> list[CheckResult]:
    """Check uv and npm tool installations from config."""
    results: list[CheckResult] = []

    uv_tools = tools_config.get("uv", [])
    if uv_tools:
        results.extend(_check_uv_tools(uv_tools))

    npm_packages = tools_config.get("npm", [])
    if npm_packages:
        results.extend(_check_npm_packages(npm_packages))

    return results


def list_venvs(code_root: Path, versions: list[str]) -> list[CheckResult]:
    """Check virtual environments under code_root/venvs/."""
    venvs_dir = code_root / "venvs"
    results: list[CheckResult] = []

    if not venvs_dir.exists():
        for version in versions:
            results.append(
                CheckResult(
                    name=f"venv: {version}",
                    status=CheckStatus.WARN,
                    message="venvs/ directory does not exist",
                )
            )
        return results

    for version in versions:
        venv_path = venvs_dir / version
        python_bin = venv_path / "bin" / "python"

        if not venv_path.exists():
            results.append(
                CheckResult(
                    name=f"venv: {version}",
                    status=CheckStatus.WARN,
                    message="Not created",
                )
            )
            continue

        if not python_bin.exists():
            results.append(
                CheckResult(
                    name=f"venv: {version}",
                    status=CheckStatus.WARN,
                    message="Missing bin/python",
                )
            )
            continue

        try:
            proc = subprocess.run(  # noqa: S603
                [str(python_bin), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            py_version = (proc.stdout or proc.stderr or "").strip()
            # Extract just the version number e.g. "Python 3.12.3" → "3.12.3"
            py_ver_clean = py_version.replace("Python ", "").strip() or "?"
            results.append(
                CheckResult(
                    name=f"venv: {version}",
                    status=CheckStatus.OK,
                    message=f"Python {py_ver_clean}",
                )
            )
        except Exception:
            results.append(
                CheckResult(
                    name=f"venv: {version}",
                    status=CheckStatus.WARN,
                    message="bin/python exists but could not run",
                )
            )

    return results


def run_doctor(code_root: Path) -> dict[str, list[CheckResult]]:
    """Run all health checks and return grouped results."""
    groups: dict[str, list[CheckResult]] = {}

    # --- Configuration ---
    config_result = check_config(code_root)
    groups["Configuration"] = [config_result]

    # Try to load config for downstream checks
    config: ConfigModel | None = None
    config_path = code_root / "config.toml"
    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                raw = tomli.load(f)
            config = ConfigModel(**raw)
        except Exception:
            # Config load failed; skip downstream checks, will use empty config
            config = None

    # --- Connectivity ---
    groups["Connectivity"] = [check_github_ssh()]

    # --- Tools ---
    tool_results = check_system_tools()

    if config and (config.tools.uv or config.tools.npm):
        tools_config = {
            "uv": config.tools.uv,
            "npm": config.tools.npm,
        }
        tool_results.extend(check_tool_versions(tools_config))

    groups["Tools"] = tool_results

    # --- Virtual Environments ---
    versions = config.versions if config else []
    groups["Virtual Environments"] = list_venvs(code_root, versions)

    return groups
