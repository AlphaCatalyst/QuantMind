#!/bin/sh
set -eu

REPOSITORY_ROOT="/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com"
PYTHON_BIN="/Users/yj/Documents/Codex/2026-06-30/nih/work/QuantMind/.venv/bin/python"
LIBOMP_DIR="/Users/yj/Documents/Codex/2026-06-30/nih/work/AlphaQuant/third-party/runtime/libomp/libomp/22.1.8/lib"
TRIGGER="${1:-launchd}"

cd "$REPOSITORY_ROOT"

if [ ! -x "$PYTHON_BIN" ]; then
  echo '{"status":"blocked","error_class":"model_failure","reason":"python_runtime_unavailable"}' >&2
  exit 69
fi

if [ -z "${TUSHARE_TOKEN:-}" ]; then
  echo '{"status":"blocked","error_class":"credential_failure","reason":"launch_context_token_unavailable"}' >&2
  exit 78
fi

export DYLD_LIBRARY_PATH="$LIBOMP_DIR${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
exec "$PYTHON_BIN" \
  "$REPOSITORY_ROOT/tools/quantmind2/manage_fresh_heartbeat_launchagent.py" \
  run-now --trigger "$TRIGGER"
