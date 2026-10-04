# WasmBox

Secure multi-tenant Python plugin sandbox using WebAssembly (Wasmtime), with a React and Monaco developer portal.

## Folders

| Folder | What it holds | Owner |
|---|---|---|
| `backend/app/api/` | The web server: receives requests and sends answers | Vineet |
| `backend/app/runtime/` | Runs `.wasm` files safely from Python | Prathamesh |
| `backend/tests/` | Automatic checks that prove things work | Priya |
| `backend/scripts/` | Small helper scripts you run by hand | Prathamesh |
| `frontend/` | The website in the browser (React and Monaco) | Sashmita |
| `plugins/benign/` | Safe test programs | Prathamesh |
| `plugins/malicious/` | Attack programs we use to test our security | Priya |
| `docs/` | Our notes, findings and explanations | Everyone |

## Rules

- One branch per task, named `yourname/short-task`
- Small pull requests, and nobody merges their own
- Stuck for 90 minutes? Ask in the team chat

## How to run

Coming as the project grows.