# WasmBox API Server

**Owner:** Vineet

The web server receives requests from the frontend or external clients and orchestrates code execution.

## Endpoints

- `GET /health`: Healthcheck endpoint returning `{"ok": true}`.
- `POST /run`: Accepts JSON payload `{"code": "..."}` and returns execution status, output, and telemetry conforming to `docs/API_CONTRACT.md`.

## Week 1 Status

- Dependencies pinned in `requirements.txt`.
- Data transfer schemas defined in `schemas.py`.
- Mock implementation for `/run` simulating code execution.
