#!/usr/bin/env bash
# test.sh — run every smithy test with the libraries the engine needs, the same way CI does.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null 2>&1 || { echo "error: uv is needed (https://docs.astral.sh/uv/); or install pydantic pyyaml python-dotenv rich pytest" >&2; exit 2; }
W=(--with pytest --with pydantic --with pyyaml --with python-dotenv --with rich)
uv run "${W[@]}" python -m unittest discover -s runner/tests
uv run "${W[@]}" python -m pytest -q tests
