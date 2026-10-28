# API Contract

This is what the frontend (Sashmita) and the backend (Vineet) agree on.
Don't change it without telling the team.

## GET /health

Checks the server is running.

Response:
```json
{ "ok": true }
```

## POST /run

Sends the user's Python code to run.

Request:
```json
{ "code": "print('hi')" }
```

Response:
```json
{
  "status": "ok",
  "stdout": "hi\n",
  "stderr": "",
  "exec_ms": 0,
  "mem_bytes": 0
}
```

## Fields

| Field | Type | Meaning |
|---|---|---|
| `status` | string | One of `ok`, `error`, `denied`, `timeout`, `memory_exceeded` |
| `stdout` | string | What the plugin printed |
| `stderr` | string | Error output, empty if none |
| `exec_ms` | number | Execution time in milliseconds |
| `mem_bytes` | number | Memory used, in bytes |

## Status meanings

- `ok`: the plugin ran and finished
- `error`: the plugin crashed or has a syntax error
- `denied`: the plugin tried something the sandbox blocks (files, network)
- `timeout`: the plugin ran too long and was stopped
- `memory_exceeded`: the plugin used too much memory and was stopped

## Week 2 note

The five-field response shape is the same as Week 1. Real execution is now wired up.
`exec_ms` and `mem_bytes` remain `0` until Week 3.

## Input validation rules

| Input | HTTP status | Response |
|---|---|---|
| `code` field missing from JSON body | **422** (FastAPI validation error) | FastAPI's default error body — no `stderr` field. **Sashmita: handle 422 separately from the five-field error response.** |
| `code` is empty string or whitespace only | 200 | `{"status": "error", "stderr": "No code provided", "stdout": "", "exec_ms": 0, "mem_bytes": 0}` |
| `code` exceeds 10,000 characters | 200 | `{"status": "error", "stderr": "Code exceeds maximum allowed size of 10000 characters ...", "stdout": "", "exec_ms": 0, "mem_bytes": 0}` |

## Changing this contract

1. Open a PR that edits this file
2. Vineet and Sashmita both approve
3. Then change the code



## Notes

1. The `code` field is required. A missing `code` returns HTTP 422 (FastAPI validation), which does **not** follow the five-field schema. Frontend must handle 422 separately.
2. Empty or whitespace-only code returns a normal 200 with `status: "error"` and `stderr: "No code provided"`.
3. Code longer than 10,000 characters is rejected before execution with `status: "error"` and a clear size message.
4. Frontend Editor Integration: Confirmed frontend Monaco editor state binds directly to string payload in `{"code": "..."}`. CORS headers on backend explicitly allow preflight OPTIONS requests from `http://localhost:5173`.