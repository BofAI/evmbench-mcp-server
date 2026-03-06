# evmBench-mcp-server backend

This directory contains the backend services and worker orchestration.

## Build images

```bash
# base
docker build -t evmbench/base:latest -f docker/base/Dockerfile .

# worker
docker build -t evmbench/worker:latest -f docker/worker/Dockerfile .

# backend (api + instancer + secretsvc + resultsvc + oai_proxy + prunner)
docker build -t evmbench/backend:latest -f docker/backend/Dockerfile .
```

## Daily worker limit

Instancer enforces a **global per-day limit** on how many workers can be started.

- Configure via `INSTANCER_DAILY_WORKER_LIMIT` (integer, default `100` when unset).
- The limit is evaluated in UTC days (00:00–24:00 UTC).
- When the limit is reached:
  - New jobs are marked as `failed` without starting a worker.
  - Instancer logs a warning including the `job_id` and date.
- Usage is tracked in the `instancer_daily_usage` table (date, capacity, used_count).

The backend exposes a helper endpoint for UIs and MCP tools:

- `GET /v1/jobs/daily-limit`
  - Returns:
    - `date_utc`: current UTC date.
    - `capacity`: configured daily capacity for that date.
    - `used`: number of successfully started workers.
    - `remaining`: `max(capacity - used, 0)`.
    - `reset_at`: ISO8601 timestamp when the quota resets (next UTC midnight).

## Local run (recommended)

```bash
cp .env.example .env
# For local dev, the placeholder secrets in .env.example are sufficient.
# For internet-exposed deployments, replace them with strong values.
docker compose up -d --build
```

Proxy-token mode (optional):

```bash
# set BACKEND_OAI_KEY_MODE=proxy and OAI_PROXY_AES_KEY=... in .env
docker compose --profile proxy up -d --build
```

## k8s development
```bash
# install kind from https://kind.sigs.k8s.io/docs/user/quick-start/
kind create cluster --name evmbench --config kind-config.yaml
kind load --name evmbench docker-image evmbench/worker:latest

# after finishing development:
kind delete cluster --name evmbench
```
