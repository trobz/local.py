from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import jsonschema
import typer

# Maps CLI-emitted detector names to .odoo-dev.json schema enum values.
_DETECTOR_NAME_MAP = {
    "Trobz": "trobz",
    "Camptocamp": "c2c",
    "Camptocamp (Legacy)": "c2c",
    "odoo.sh": "odoosh",
    "Doodba": "doodba",
}

_SCHEMA_PATH = Path(__file__).parent / "assets" / "odoo-dev.json"

_MANAGED_LAYOUTS = frozenset(_DETECTOR_NAME_MAP)


def _load_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text())


# ---------------------------------------------------------------------------
# CLI subprocess helper
# ---------------------------------------------------------------------------


def _run_addons_path_cli(cwd: Path) -> dict | None:
    """Run ``odoo-addons-path --format json <cwd>`` and return parsed JSON.

    Returns None on missing binary, non-zero exit, timeout, or JSON parse error.
    The caller treats None as "no managed layout detected".
    """
    try:
        proc = subprocess.run(  # noqa: S603
            ["odoo-addons-path", "--format", "json", str(cwd)],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            typer.secho(
                f"odoo-addons-path exited {proc.returncode}; falling through to local",
                fg=typer.colors.YELLOW,
                err=True,
            )
            return None
        return json.loads(proc.stdout)
    except FileNotFoundError:
        typer.secho("odoo-addons-path not found; falling through to local", fg=typer.colors.YELLOW, err=True)
        return None
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        typer.secho(
            f"odoo-addons-path unusable ({exc}); falling through to local",
            fg=typer.colors.YELLOW,
            err=True,
        )
        return None


# ---------------------------------------------------------------------------
# Git-branch version fallback (patchable in tests)
# ---------------------------------------------------------------------------


def _git_branch_version(cwd: Path) -> str | None:
    """Return the version prefix from the current git branch, or None."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],  # noqa: S607
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=5,
        )
        if result.returncode == 0:
            match = re.match(r"^(\d+\.\d+)", result.stdout.strip())
            if match:
                return match.group(1)
    except Exception:  # noqa: S110
        pass
    return None


# ---------------------------------------------------------------------------
# Core resolution
# ---------------------------------------------------------------------------


def _build_managed_block(
    layout_name: str, odoo_dir: list, version: str | None, cwd: Path, code_dir: Path
) -> dict | None:
    """Return managed-layout odoo block, or None to fall through."""
    schema_layout = _DETECTOR_NAME_MAP[layout_name]
    source_paths = [str(p) for p in odoo_dir if Path(p).is_dir()]
    if not source_paths:
        typer.secho(
            f"{layout_name} detected but no odoo_dir entries exist on disk ({odoo_dir}); falling through to local",
            fg=typer.colors.YELLOW,
            err=True,
        )
        return None
    block: dict = {"layout": schema_layout, "sourcePaths": source_paths}
    if version:
        block["version"] = version
    enterprise_paths = _derive_enterprise_paths(layout=schema_layout, cwd=cwd, code_dir=code_dir, version=version)
    if enterprise_paths:
        block["enterprisePaths"] = enterprise_paths
    return block


def _build_local_block(version: str, cwd: Path, code_dir: Path) -> dict | None:
    """Return local-layout odoo block, or None when checkout is absent/empty."""
    checkout_root = code_dir / "odoo" / "odoo" / version
    if not checkout_root.exists():
        return None
    source_paths = _derive_local_source_paths(checkout_root)
    if not source_paths:
        return None
    block: dict = {"layout": "local", "version": version, "sourcePaths": source_paths}
    enterprise_paths = _derive_enterprise_paths(layout="local", cwd=cwd, code_dir=code_dir, version=version)
    if enterprise_paths:
        block["enterprisePaths"] = enterprise_paths
    return block


def resolve_odoo_config(cwd: Path, code_dir: Path) -> dict:
    """Detect Odoo layout and build the ``odoo`` block for odoo-dev.json."""
    cli = _run_addons_path_cli(cwd)

    layout_name = cli.get("layout") if cli else None
    odoo_dir = cli.get("odoo_dir", []) if cli else []
    version = cli.get("version") if cli else None

    if layout_name in _MANAGED_LAYOUTS and odoo_dir:
        block = _build_managed_block(layout_name, odoo_dir, version, cwd, code_dir)
        if block is not None:
            return block

    if not version:
        version = _git_branch_version(cwd)

    if version:
        block = _build_local_block(version, cwd, code_dir)
        if block is not None:
            return block

    typer.secho(
        "Could not resolve an Odoo source layout. "
        "Expected a managed odoo-addons-path layout or a local checkout under "
        f"{code_dir / 'odoo' / 'odoo' / '<version>'}.",
        fg=typer.colors.RED,
        err=True,
    )
    raise typer.Exit(code=1)


def _resolve_symlink(path: Path) -> str:
    """Return the absolute, symlink-resolved path as a string."""
    return str(path.resolve(strict=False))


def _derive_enterprise_paths(
    *,
    layout: str,
    cwd: Path,
    code_dir: Path,
    version: str | None,
) -> list[str]:
    """Return enterprise addon paths for the detected layout, or []."""
    if layout == "odoosh":
        candidate = cwd / "enterprise"
        if candidate.is_dir():
            return [_resolve_symlink(candidate)]
        return []

    if layout in {"trobz", "local"} and version:
        candidate = code_dir / "odoo" / "enterprise" / version
        if candidate.is_dir():
            return [_resolve_symlink(candidate)]
        return []

    # c2c / doodba: no convention yet
    return []


def _derive_local_source_paths(checkout_root: Path) -> list[str]:
    """Return existing standard addons dirs under a local Odoo checkout."""
    candidates = [
        checkout_root / "addons",
        checkout_root / "odoo" / "addons",
    ]
    return [str(p) for p in candidates if p.is_dir()]


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


def write_odoo_dev_config(
    target_dir: Path,
    odoo_block: dict,
    *,
    force: bool = False,
) -> None:
    """Write (or overwrite) odoo-dev.json in target_dir.

    - Backs up existing file to .odoo-dev.json.bak before overwrite.
    - Merges: replaces only the ``odoo`` key; sibling keys are preserved.
    - Validates result against the JSON Schema before writing.
    - Uses atomic write (.tmp → os.replace).
    """
    config_file = target_dir / ".odoo-dev.json"
    tmp_file = target_dir / ".odoo-dev.json.tmp"
    bak_file = target_dir / ".odoo-dev.json.bak"

    existing_data: dict = {}
    if config_file.exists():
        shutil.copy2(str(config_file), str(bak_file))
        if not force and not typer.confirm(f"{config_file} already exists. Overwrite?", default=False):
            raise typer.Abort()
        try:
            existing_data = json.loads(config_file.read_text())
        except json.JSONDecodeError:
            existing_data = {}

    # Merge: replace odoo key, keep siblings
    new_data = {**existing_data, "odoo_source": odoo_block}

    # Validate
    schema = _load_schema()
    jsonschema.validate(new_data, schema)

    # Print resolved sourcePaths so user sees what was cached
    typer.secho("Resolved sourcePaths:", fg=typer.colors.CYAN)
    for sp in odoo_block.get("sourcePaths", []):
        typer.echo(f"  {sp}")
    enterprise_paths = odoo_block.get("enterprisePaths")
    if enterprise_paths:
        typer.secho("Resolved enterprisePaths:", fg=typer.colors.CYAN)
        for ep in enterprise_paths:
            typer.echo(f"  {ep}")

    # Atomic write
    tmp_file.write_text(json.dumps(new_data, indent=2) + "\n")
    os.replace(str(tmp_file), str(config_file))

    typer.secho(f"Written: {config_file}", fg=typer.colors.GREEN)
