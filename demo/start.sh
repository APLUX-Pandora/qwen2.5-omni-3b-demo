#!/bin/sh
set -eu
DEMO_REPO=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OMNI_PYTHON=${OMNI_PYTHON:-$DEMO_REPO/.venv/bin/python}
OMNI_MODEL_DIR=${OMNI_MODEL_DIR:-$DEMO_REPO/models}
OMNI_RUN_DIR=${OMNI_RUN_DIR:-$DEMO_REPO/run}
if [ ! -x "$OMNI_PYTHON" ]; then
  echo "The isolated Python environment is required." >&2
  exit 1
fi
cd "$DEMO_REPO"
exec "$OMNI_PYTHON" -m demo.server --model "$OMNI_MODEL_DIR" --run-dir "$OMNI_RUN_DIR" "$@"
