#!/bin/sh
set -eu

RUNTIME_ROOT="${HOME}/Library/Application Support/QuantMind"
CONFIG="${RUNTIME_ROOT}/config/runtime.json"
PYTHON="${RUNTIME_ROOT}/runtime/current-env/bin/python"
APP="${RUNTIME_ROOT}/runtime/current-app"
TRIGGER="${1:-launchd}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
TMP_ROOT="${RUNTIME_ROOT}/state/tmp"
RUN_TMP="${TMP_ROOT}/${RUN_ID}"
TMP_STATUS="${RUNTIME_ROOT}/logs/fresh-heartbeat-tmp-cleanup.status.json"
MANAGER="${APP}/tools/quantmind2/manage_fresh_runtime_deployment.py"
child_pid=""
cleanup_done=0

cleanup_runtime_tmp() {
  if [ "${cleanup_done}" -eq 1 ]; then
    return 0
  fi
  cleanup_done=1
  mkdir -p "${RUNTIME_ROOT}/logs"
  cleanup_status="${TMP_STATUS}.$$"
  set +e
  if [ -n "${child_pid}" ]; then
    "${PYTHON}" "${MANAGER}" \
      --repository-root "${APP}" \
      --runtime-root "${RUNTIME_ROOT}" \
      cleanup-owned-scheduler-lock \
      --run-id "${RUN_ID}" --owner-pid "${child_pid}" >/dev/null 2>/dev/null
  fi
  "${PYTHON}" "${MANAGER}" \
    --repository-root "${APP}" \
    --runtime-root "${RUNTIME_ROOT}" \
    cleanup-runtime-tmp --run-id "${RUN_ID}" >"${cleanup_status}" 2>/dev/null
  cleanup_rc=$?
  if [ "${cleanup_rc}" -ne 0 ]; then
    printf '%s\n' '{"schema_version":"fresh-runtime-tmp-cleanup-status-v1","status":"cleanup_failed"}' >"${cleanup_status}"
  fi
  chmod 600 "${cleanup_status}" 2>/dev/null || true
  mv -f "${cleanup_status}" "${TMP_STATUS}" 2>/dev/null || true
  set -e
  return 0
}

handle_signal() {
  signal_code="$1"
  if [ -n "${child_pid}" ]; then
    kill -TERM "${child_pid}" 2>/dev/null || true
    wait "${child_pid}" 2>/dev/null || true
  fi
  cleanup_runtime_tmp
  exit "${signal_code}"
}

trap cleanup_runtime_tmp EXIT
trap 'handle_signal 129' HUP
trap 'handle_signal 130' INT
trap 'handle_signal 143' TERM

if [ ! -r "${CONFIG}" ] || [ ! -x "${PYTHON}" ] || [ ! -d "${APP}" ]; then
  echo '{"status":"blocked","reason":"runtime_deployment_incomplete"}' >&2
  exit 69
fi
if [ -z "${TUSHARE_TOKEN:-}" ]; then
  echo '{"status":"blocked","reason":"launch_context_token_unavailable"}' >&2
  exit 78
fi

"${PYTHON}" "${MANAGER}" \
  --repository-root "${APP}" \
  --runtime-root "${RUNTIME_ROOT}" \
  cleanup-stale-runtime-tmp >/dev/null
"${PYTHON}" "${MANAGER}" \
  --repository-root "${APP}" \
  --runtime-root "${RUNTIME_ROOT}" \
  create-runtime-tmp --run-id "${RUN_ID}" --owner-pid "$$" >/dev/null
export TMPDIR="${RUN_TMP}"
export QM2_RUNTIME_RUN_ID="${RUN_ID}"
cd "${RUNTIME_ROOT}"
"${PYTHON}" "${MANAGER}" \
  --repository-root "${APP}" \
  --runtime-root "${RUNTIME_ROOT}" \
  run-now --trigger "${TRIGGER}" &
child_pid=$!
set +e
wait "${child_pid}"
heartbeat_rc=$?
set -e
child_pid=""
cleanup_runtime_tmp
exit "${heartbeat_rc}"
