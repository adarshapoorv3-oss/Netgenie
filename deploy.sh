#!/usr/bin/env bash
# One-click deploy for the OPEA Innovation Challenge submission.
# Target: clean environment -> running system in well under 10 minutes.
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker &> /dev/null; then
  echo "Docker is required. Install Docker Desktop / Docker Engine and re-run." >&2
  exit 1
fi

if ! docker compose version &> /dev/null; then
  echo "Docker Compose v2 is required (the 'docker compose' subcommand)." >&2
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example (MOCK_LLM=true — no model download needed)."
fi

echo "Building and starting the mega-service (guardrails, retrieval, telemetry, gateway)..."
docker compose up --build -d guardrails retrieval_worker telemetry_worker gateway

echo -n "Waiting for gateway to become healthy"
for _ in $(seq 1 60); do
  if curl -sf http://localhost:9000/health > /dev/null 2>&1; then
    echo ""
    echo "NetGenie is up: http://localhost:9000"
    echo "Try:  curl -s -X POST http://localhost:9000/v1/chat -H 'Content-Type: application/json' -d '{\"message\":\"What is the dropped call rate in the South region?\"}'"
    exit 0
  fi
  echo -n "."
  sleep 2
done

echo ""
echo "Gateway did not become healthy in time. Check logs with: docker compose logs -f" >&2
exit 1
