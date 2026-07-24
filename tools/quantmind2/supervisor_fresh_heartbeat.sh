#!/bin/sh
set -eu

REPOSITORY_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
exec "${PYTHON:-python3}" \
  "$REPOSITORY_ROOT/tools/quantmind2/run_autonomous_research_supervisor.py" \
  run-fresh-heartbeat "$@"
