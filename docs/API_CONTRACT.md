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

## Week 1 note

`/run` is a **mock** this week. It always returns `status: "ok"` and a fake `stdout`.
Real execution starts in Week 2. The shape of the response stays exactly the same.

## Changing this contract

1. Open a PR that edits this file
2. Vineet and Sashmita both approve
3. Then change the code