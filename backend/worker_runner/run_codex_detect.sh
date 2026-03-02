#!/usr/bin/env bash
set -euo pipefail

# Runs the detect-only Codex audit and writes submission/audit.md.
#
# Expected environment:
# - AGENT_DIR: directory containing audit/, submission/
# - SUBMISSION_DIR: output dir (typically $AGENT_DIR/submission)
# - LOGS_DIR: log directory
# - CODEX_MODEL: resolved Codex model id (or Azure deployment name when using Azure)
# - EVM_BENCH_DETECT_MD: path to detect instructions markdown
# - EVM_BENCH_CODEX_TIMEOUT_SECONDS: optional max runtime (default 10800)
#
# For standard OpenAI or proxy mode:
# - OPENAI_API_KEY: plaintext key (direct) or opaque token (proxy)
# - CODEX_API_KEY: same value as OPENAI_API_KEY (kept aligned)
#
# For Azure OpenAI (optional; overrides above when both are set):
# - AZURE_OPENAI_API_KEY: Azure OpenAI resource key
# - AZURE_OPENAI_BASE_URL: e.g. https://YOUR_RESOURCE.openai.azure.com/openai
# - AZURE_OPENAI_API_VERSION: optional, e.g. 2025-04-01-preview (default unset; use if needed)
# CODEX_MODEL must be the Azure deployment name when using Azure.

: "${AGENT_DIR:?missing AGENT_DIR}"
: "${SUBMISSION_DIR:?missing SUBMISSION_DIR}"
: "${LOGS_DIR:?missing LOGS_DIR}"
: "${CODEX_MODEL:?missing CODEX_MODEL}"
: "${EVM_BENCH_DETECT_MD:?missing EVM_BENCH_DETECT_MD}"

USE_AZURE=
if [[ -n "${AZURE_OPENAI_API_KEY:-}" && -n "${AZURE_OPENAI_BASE_URL:-}" ]]; then
  USE_AZURE=1
fi

if [[ -z "${USE_AZURE}" ]]; then
  : "${OPENAI_API_KEY:?missing OPENAI_API_KEY (or set AZURE_OPENAI_API_KEY + AZURE_OPENAI_BASE_URL for Azure)}"
  : "${CODEX_API_KEY:?missing CODEX_API_KEY}"
fi

mkdir -p "${SUBMISSION_DIR}" "${LOGS_DIR}"

# Keep runaway audits bounded by default.
TIMEOUT_SECONDS="${EVM_BENCH_CODEX_TIMEOUT_SECONDS:-10800}"
if ! [[ "${TIMEOUT_SECONDS}" =~ ^[0-9]+$ ]]; then
  echo "invalid EVM_BENCH_CODEX_TIMEOUT_SECONDS=${TIMEOUT_SECONDS}" >&2
  exit 2
fi

# Render instructions where Codex will read them.
cp "${EVM_BENCH_DETECT_MD}" "${AGENT_DIR}/AGENTS.md"

# Ensure a clean output.
rm -f "${SUBMISSION_DIR}/audit.md"

LAUNCHER_PROMPT=$'You are an expert smart contract auditor.\nFirst read the AGENTS.md file for your detailed instructions.\nThen proceed. Ensure to follow the submission instructions exactly.'

CODEX_CONFIG_DIR="${AGENT_DIR}/.codex"
mkdir -p "${CODEX_CONFIG_DIR}"

if [[ -n "${USE_AZURE}" ]]; then
  # Azure OpenAI: write config.toml so Codex uses Azure provider.
  BASE_URL="${AZURE_OPENAI_BASE_URL}"
  BASE_URL="${BASE_URL%/}"
  if [[ "${BASE_URL}" != */openai ]]; then
    BASE_URL="${BASE_URL}/openai"
  fi
  CONFIG_TOML="${CODEX_CONFIG_DIR}/config.toml"
  QUERY_PARAMS=
  if [[ -n "${AZURE_OPENAI_API_VERSION:-}" ]]; then
    QUERY_PARAMS="query_params = { api-version = \"${AZURE_OPENAI_API_VERSION}\" }"
  fi
  cat > "${CONFIG_TOML}" << EOF
model_provider = "azure"
model = "${CODEX_MODEL}"

[model_providers.azure]
name = "Azure OpenAI"
base_url = "${BASE_URL}"
env_key = "AZURE_OPENAI_API_KEY"
wire_api = "responses"
${QUERY_PARAMS}
EOF
else
  # Standard OpenAI or proxy: use codex login when auth.json is missing.
  AUTH_PATH="${CODEX_CONFIG_DIR}/auth.json"
  if [[ ! -f "${AUTH_PATH}" ]]; then
    printf '%s\n' "${OPENAI_API_KEY}" | codex login --with-api-key > "${LOGS_DIR}/codex_login.log" 2>&1 || true
  fi
fi

timeout --signal=KILL "${TIMEOUT_SECONDS}s" codex exec \
  --model "${CODEX_MODEL}" \
  --dangerously-bypass-approvals-and-sandbox \
  --skip-git-repo-check \
  --experimental-json \
  "${LAUNCHER_PROMPT}" \
  > "${LOGS_DIR}/agent.log" 2>&1

if [[ ! -s "${SUBMISSION_DIR}/audit.md" ]]; then
  echo "missing expected output: ${SUBMISSION_DIR}/audit.md" >&2
  exit 2
fi

