"""Make the kebab-named script importable as a module.

``scripts/check-commit-message.py`` is hyphenated so it reads as a command,
which means it cannot be imported by name. Load it explicitly by path and
register it under an underscored module name for the tests.
"""
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "check-commit-message.py"

spec = importlib.util.spec_from_file_location("check_commit_message", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules["check_commit_message"] = module
spec.loader.exec_module(module)
