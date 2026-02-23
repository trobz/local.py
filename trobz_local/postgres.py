"""PostgreSQL user management functions for Odoo development.

OS-aware utilities for verifying and creating PostgreSQL users with CREATEDB permission.
Supports Linux (sudo -u postgres) and macOS (Homebrew direct access).
"""

import re
import shutil
import subprocess

# PostgreSQL identifier: alphanumeric and underscore, max 63 chars
_PG_USERNAME_REGEX = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")


def _get_psql_base_cmd(system: str) -> list[str]:
    """Get OS-specific base psql command.

    Args:
        system: OS name from platform.system() ("Darwin" or "Linux")

    Returns:
        Base command list for psql execution

    Raises:
        ValueError: If system is not supported
        FileNotFoundError: If psql is not installed
    """
    if system == "Darwin":
        # macOS: Homebrew PostgreSQL runs as current user
        psql_path = shutil.which("psql")
        if not psql_path:
            msg = "psql not found - install PostgreSQL via Homebrew"
            raise FileNotFoundError(msg)
        return [psql_path, "-h", "localhost", "-d", "postgres"]
    if system == "Linux":
        # Linux: Use sudo to run as postgres user
        return ["sudo", "-n", "-u", "postgres", "psql"]
    msg = f"Unsupported OS: {system}"
    raise ValueError(msg)


def validate_username(username: str) -> bool:
    """Validate PostgreSQL username format.

    Args:
        username: Username to validate

    Returns:
        True if valid PostgreSQL identifier
    """
    if not username or not isinstance(username, str):
        return False
    return bool(_PG_USERNAME_REGEX.match(username))


def validate_password(password: str) -> bool:
    """Validate password is not empty.

    Args:
        password: Password to validate

    Returns:
        True if password is non-empty string
    """
    return bool(password and isinstance(password, str))


def check_postgres_running() -> bool:
    """Check if PostgreSQL is running using pg_isready.

    Returns:
        True if PostgreSQL is accepting connections on localhost
    """
    try:
        pg_isready = shutil.which("pg_isready")
        if not pg_isready:
            return False
        result = subprocess.run(  # noqa: S603
            [pg_isready, "-h", "localhost"], capture_output=True, timeout=5
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    else:
        return result.returncode == 0


def check_user_exists(username: str, system: str) -> bool:
    """Check if PostgreSQL user exists.

    Args:
        username: Username to check
        system: OS name from platform.system()

    Returns:
        True if user exists
    """
    if not validate_username(username):
        return False
    try:
        base_cmd = _get_psql_base_cmd(system)
        query = "SELECT 1 FROM pg_roles WHERE rolname = :'username'"
        cmd = [*base_cmd, "-v", f"username={username}", "-tA", "-f", "-"]
        result = subprocess.run(  # noqa: S603
            cmd, capture_output=True, text=True, timeout=5, input=query
        )
        return result.returncode == 0 and result.stdout.strip() == "1"
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return False


def create_user(username: str, password: str, system: str) -> tuple[bool, str]:
    """Create PostgreSQL user with CREATEDB permission.

    Args:
        username: Username to create
        password: Password for the user
        system: OS name from platform.system()

    Returns:
        Tuple of (success, error_message)
    """
    if not validate_username(username) or not validate_password(password):
        return False, "Invalid username or password format"

    try:
        base_cmd = _get_psql_base_cmd(system)
        # Use psql variable binding to prevent SQL injection
        # :"varname" for identifier, :'varname' for string value
        # Use -f - (stdin) because -c doesn't support variable interpolation
        sql = "CREATE USER :\"username\" WITH PASSWORD :'password' CREATEDB;"
        cmd = [*base_cmd, "-v", f"username={username}", "-v", f"password={password}", "-f", "-"]
        result = subprocess.run(  # noqa: S603
            cmd, capture_output=True, text=True, timeout=10, input=sql
        )
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except ValueError as e:
        return False, str(e)
    except FileNotFoundError:
        return False, "psql not found"
    else:
        if result.returncode != 0:
            return False, result.stderr
        return True, ""


def verify_connection(host: str, user: str, password: str) -> bool:
    """Test PostgreSQL connection with provided credentials.

    Args:
        host: Database host
        user: Username
        password: Password

    Returns:
        True if connection successful
    """
    try:
        psql_path = shutil.which("psql")
        if not psql_path:
            return False
        # Only pass PGPASSWORD, no other environment variables
        env = {"PGPASSWORD": password}
        result = subprocess.run(  # noqa: S603
            [psql_path, "-h", host, "-U", user, "-d", "postgres", "-c", "SELECT 1;"],
            capture_output=True,
            env=env,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    else:
        return result.returncode == 0
