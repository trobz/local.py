import os
from pathlib import Path
from unittest.mock import patch

from trobz_local.utils import get_code_root


def test_get_code_root_default():
    """Returns ~/code when TLC_CODE_DIR not set."""
    with patch.dict(os.environ, {}, clear=True):
        result = get_code_root()
        assert result == Path.home() / "code"


def test_get_code_root_from_env():
    """Returns path from TLC_CODE_DIR env var."""
    with patch.dict(os.environ, {"TLC_CODE_DIR": "/custom/path"}):
        result = get_code_root()
        assert result == Path("/custom/path")


def test_get_code_root_expands_tilde():
    """Expands ~ in TLC_CODE_DIR."""
    with patch.dict(os.environ, {"TLC_CODE_DIR": "~/mycode"}):
        result = get_code_root()
        assert result == Path.home() / "mycode"
