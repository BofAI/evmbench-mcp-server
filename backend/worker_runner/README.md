# Worker runner assets

This folder contains the repo-owned assets that define the detect-only worker behavior.

The worker image copies this directory into the container at `/opt/evmbench/worker_runner/`.

## Files

- `detect.md`: the full instructions prompt copied to `$HOME/AGENTS.md` inside the worker container.
- `model_map.json`: maps UI model keys (sent as `AGENT_ID`) to Codex model IDs.
- `run_codex_detect.sh`: runs Codex once and ensures `submission/audit.md` was created.

## Using Azure OpenAI

When running with Azure OpenAI, set (e.g. in .env / instancer env):

- `AZURE_OPENAI_API_KEY`: your Azure OpenAI resource key
- `AZURE_OPENAI_BASE_URL`: e.g. `https://YOUR_RESOURCE.openai.azure.com/openai`
- `AZURE_OPENAI_API_VERSION`: optional; e.g. `2025-04-01-preview` if required
- `AZURE_OPENAI_DEPLOYMENT`: the single Azure deployment name (used as CODEX_MODEL; no model_map)

The script writes a Codex `config.toml` for the Azure provider and skips `OPENAI_API_KEY` / codex login. When the instancer passes these env vars, the worker uses `AZURE_OPENAI_DEPLOYMENT` as the model and ignores frontend model selection for Azure.

## Editing guidelines

- Prefer updating `detect.md` rather than hardcoding prompts in Python.
- Keep `model_map.json` in sync with the model options in the frontend.
- If you change where these files live in the image, update `backend/docker/worker/Dockerfile` and `backend/docker/worker/init.py`.

