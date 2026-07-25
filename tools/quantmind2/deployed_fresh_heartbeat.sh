#!/bin/sh
set -eu

RUNTIME_ROOT="${HOME}/Library/Application Support/QuantMind"
CONFIG="${RUNTIME_ROOT}/config/runtime.json"
PYTHON="${RUNTIME_ROOT}/runtime/current-env/bin/python"
APP="${RUNTIME_ROOT}/runtime/current-app"
TRIGGER="${1:-launchd}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
RUN_TMP="${RUNTIME_ROOT}/state/tmp/${RUN_ID}"

cleanup() {
  if [ -d "${RUN_TMP}" ]; then
    find "${RUN_TMP}" -depth -delete
  fi
}
trap cleanup EXIT HUP INT TERM

if [ ! -r "${CONFIG}" ] || [ ! -x "${PYTHON}" ] || [ ! -d "${APP}" ]; then
  echo '{"status":"blocked","reason":"runtime_deployment_incomplete"}' >&2
  exit 69
fi
if [ -z "${TUSHARE_TOKEN:-}" ]; then
  echo '{"status":"blocked","reason":"launch_context_token_unavailable"}' >&2
  exit 78
fi

mkdir -p "${RUN_TMP}"
export TMPDIR="${RUN_TMP}"
cd "${RUNTIME_ROOT}"
exec "${PYTHON}" \
  "${APP}/tools/quantmind2/manage_fresh_runtime_deployment.py" \
  --repository-root "${APP}" \
  --runtime-root "${RUNTIME_ROOT}" \
  run-now --trigger "${TRIGGER}"
