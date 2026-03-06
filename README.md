# evmBench-mcp-server

[![Apache-2.0 License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

MCP server and web interface for smart contract audits. Upload contract source code, select a model, and receive a structured vulnerability report. Based on [evmBench](https://github.com/openai/frontier-evals); adds MCP (Model Context Protocol) endpoints for agents and tools.

## Background

This project is maintained by **BankofAI** and is **based on** [evmBench](https://github.com/openai/frontier-evals). We extended the original codebase with:

- **Original audit service** — Web UI and API for submitting contracts and running the detect-only Codex agent, unchanged in spirit.
- **MCP integration** — New MCP (Model Context Protocol) endpoints so other agents or MCP-enabled tools can trigger audits and consume results programmatically.

If you need to run smart-contract audits from an MCP client or another agent, this project provides the necessary APIs and tool definitions.

## Features

- **Web UI** — Upload a zip of contract sources, choose a model, and view the vulnerability report with file navigation and annotations.
- **REST API** — Job submission, status, history, and daily limit (`/v1/jobs/start`, `/v1/jobs/{id}`, `/v1/jobs/history`, `/v1/jobs/daily-limit`).
- **MCP API** — Tools callable via MCP for starting jobs and querying results (see [backend/README.md](backend/README.md) for MCP setup).
- **Flexible backends** — Worker execution via Docker (default) or optional Kubernetes.
- **OpenAI / Azure** — Support for direct API key, proxy-token mode, or Azure OpenAI (single deployment).

## How it works

### Architecture

```
Frontend (Next.js)
    │
    ├─ POST /v1/jobs/start ───► Backend API (FastAPI, port 1337)
    ├─ GET  /v1/jobs/{id}           ├─► PostgreSQL (job state)
    ├─ GET  /v1/jobs/history        ├─► Secrets Service (port 8081)
    ├─ GET  /v1/jobs/daily-limit    └─► RabbitMQ (job queue)
    └─ MCP tools
                                             │
                                        Instancer (consumer)
                                              │
                                    ┌─────────┴──────────┐
                                    ▼                    ▼
                              Docker backend       K8s backend (optional)
                                    │                    │
                                    └────────┬───────────┘
                                             ▼
                                      Worker container
                                        ├─► Secrets Service (fetch bundle)
                                        ├─► (optional) OAI Proxy / Azure OpenAI
                                        └─► Results Service (port 8083)
```

### Flow

1. User or MCP client submits a zip of contract files (and optionally an OpenAI API key) to the backend.
2. Backend creates a job in Postgres, stores a secret bundle in the Secrets Service, and publishes to RabbitMQ.
3. Instancer consumes the message and starts a worker (Docker or K8s).
4. Worker fetches the bundle, extracts the zip to `audit/`, and runs the Codex detect-only agent (see `backend/worker_runner/`).
5. The agent writes `submission/audit.md`. The worker validates the JSON report and uploads it to the Results Service.
6. Frontend or MCP client polls job status and displays the report.

## Security

The worker runs an LLM-driven agent against **untrusted** uploaded code. Treat the worker runtime (filesystem, logs, outputs) as untrusted.

See [SECURITY.md](SECURITY.md) for the trust model and operational guidance.

**Credential handling:**

- **Direct BYOK (default)** — Worker receives a plaintext OpenAI key.
- **Proxy-token mode** — Worker receives an opaque token; requests go through `oai_proxy` (key never leaves the proxy).
- **Azure OpenAI** — Configure `AZURE_OPENAI_*`; worker uses a single deployment name from env.

## Getting started

### Prerequisites

- Docker
- [Bun](https://bun.sh) (for frontend)

### 1. Build base and worker images

```bash
cd backend
docker build -t evmbench/base:latest -f docker/base/Dockerfile .
docker build -t evmbench/worker:latest -f docker/worker/Dockerfile .
```

### 2. Configure and start the stack

```bash
cp .env.example .env
# Edit .env: set DATABASE_DSN, RABBITMQ_DSN, BACKEND_JWT_SECRET, etc.
# For proxy-token mode: BACKEND_OAI_KEY_MODE=proxy, OAI_PROXY_AES_KEY=...
docker compose up -d --build
```

### 3. Start the frontend

```bash
cd frontend
bun install
bun dev
```

- **Frontend:** http://127.0.0.1:3000  
- **Backend config:** http://127.0.0.1:1337/v1/integration/frontend  

See [backend/README.md](backend/README.md) for MCP, env vars, and deployment details.

## Key services

| Service     | Port  | Description                          |
|------------|-------|--------------------------------------|
| backend    | 1337  | Main API + MCP; jobs, auth, integration |
| secretsvc  | 8081  | Per-job secret bundles               |
| resultsvc  | 8083  | Worker result ingestion              |
| oai_proxy  | 8084  | Optional OpenAI proxy                |
| instancer  | —     | RabbitMQ consumer; starts workers    |
| Postgres   | 5432  | Job state                            |
| RabbitMQ   | 5672  | Job queue                            |

## Project structure

```
.
├── README.md
├── SECURITY.md
├── LICENSE
├── frontend/           Next.js UI (upload, model selection, report view)
├── backend/
│   ├── api/            FastAPI API (jobs, auth, integration, MCP)
│   ├── instancer/      RabbitMQ consumer; Docker/K8s worker launcher
│   ├── secretsvc/      Bundle storage
│   ├── resultsvc/      Result ingestion + DB
│   ├── oai_proxy/      Optional OpenAI proxy (profile: proxy)
│   ├── prunner/        Optional cleanup of stale workers (profile: cleanup)
│   ├── worker_runner/  Detect prompt, model map, Codex runner script
│   ├── docker/         Base, backend, and worker images
│   └── compose.yml     Full stack
└── deploy/             Deployment scripts (e.g. GCE)
```

## License

This codebase is **based on** [evmBench](https://github.com/openai/frontier-evals) and is used under the same terms: **Apache-2.0**. The [LICENSE](LICENSE) file in this repository applies to the code herein. Modifications and additions (including MCP integration) are by BankofAI.

## Acknowledgments

- [evmBench / frontier-evals](https://github.com/openai/frontier-evals) — Original benchmark and agent harness.
- OtterSec team (es3n1n, jktrn, TrixterTheTux, sahuang) — Frontend and tooling support.
