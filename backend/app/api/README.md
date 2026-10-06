# WasmBox API Server

**Owner:** Vineet

The web server receives requests from the frontend or external clients and orchestrates code execution.

## Endpoints

- `GET /health`: Healthcheck endpoint returning `{"ok": true}`.
- `POST /run`: Accepts JSON payload `{"code": "..."}` and returns execution status, output, and telemetry conforming to `docs/API_CONTRACT.md`.

## Running the API Server

From the `backend/` directory:

```bash
# Activate virtual environment
source .venv/bin/activate  # On Linux/macOS
# or .venv\Scripts\activate on Windows

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Running Tests

From the `backend/` directory:

```bash
pytest -q
```

## CORS Configuration

CORS middleware is enabled in `app/main.py` allowing cross-origin requests from the React frontend running on `http://localhost:5173` and `http://127.0.0.1:5173`.
