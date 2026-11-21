"""The smithy's tests need the engine's own libraries (pydantic, pyyaml, python-dotenv, rich).

On a clean checkout with a bare system Python they are not there, and the tests used to
fail with an import error that looked like a broken smithy. Now each module that needs them
is SKIPPED with the one command that runs it properly (scripts/test.sh), never failed.
"""
import importlib.util
import unittest

NEEDED = ("pydantic", "yaml", "dotenv", "rich")
RUN = "scripts/test.sh  (or: uv run --with pytest --with pydantic --with pyyaml --with python-dotenv --with rich python -m pytest -q tests)"


def require() -> None:
    missing = [m for m in NEEDED if importlib.util.find_spec(m) is None]
    if missing:
        raise unittest.SkipTest(f"needs {', '.join(missing)} — run: {RUN}")
