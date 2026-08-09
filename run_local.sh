#!/usr/bin/env bash
# Runs all four services directly with uvicorn -- no Docker required.
# Useful for quick local development, CI smoke tests, or judging on a
# machine without Docker available.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --quiet --disable-pip-version-check -r requirements-dev.txt

export PYTHONPATH="$(pwd)"
export MOCK_LLM="${MOCK_LLM:-true}"
export GUARDRAILS_URL="http://localhost:${GUARDRAILS_PORT:-6001}"
export RETRIEVAL_URL="http://localhost:${RETRIEVAL_PORT:-6002}"
export TELEMETRY_URL="http://localhost:${TELEMETRY_PORT:-6003}"

mkdir -p .run
run() {
  local name=$1 module=$2 port=$3
  echo "Starting $name on :$port"
  nohup .venv/bin/uvicorn "$module" --host 0.0.0.0 --port "$port" \
    > ".run/${name}.log" 2>&1 &
  echo $! > ".run/${name}.pid"
}

run guardrails services.guardrails.app:app "${GUARDRAILS_PORT:-6001}"
run retrieval_worker services.retrieval_worker.app:app "${RETRIEVAL_PORT:-6002}"
run telemetry_worker services.telemetry_worker.app:app "${TELEMETRY_PORT:-6003}"
sleep 1
run gateway services.gateway.app:app "${GATEWAY_PORT:-9000}"

echo -n "Waiting for gateway"
for _ in $(seq 1 30); do
  if curl -sf "http://localhost:${GATEWAY_PORT:-9000}/health" > /dev/null 2>&1; then
    echo ""
    echo "NetGenie is up: http://localhost:${GATEWAY_PORT:-9000}"
    echo "Logs: .run/*.log   Stop with: ./stop_local.sh"
    exit 0
  fi
  echo -n "."
  sleep 1
done
echo ""
echo "Gateway did not come up in time -- check .run/*.log" >&2
exit 1
