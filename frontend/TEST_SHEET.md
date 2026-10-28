# WasmBox Sandbox - Test Sheet

## 1. Python Code Runner Tests

| No. | Input / Action | Expected Result | Observed Result | Result |
|---|---|---|---|---|
| 1 | `print("hi")` | Output: hi | Output displayed | PASS |
| 2 | Two print statements | Both lines displayed | Both lines displayed | PASS |
| 3 | Invalid Python syntax | Syntax error displayed | Syntax error displayed | PASS |
| 4 | `1/0` | Division-by-zero error | Error displayed | PASS |
| 5 | Empty code | Friendly validation message | Prompt displayed | PASS |
| 6 | Loop printing 0–2 | Output: 0, 1, 2 | Output displayed | PASS |
| 7 | Stop backend and run code | Friendly server-unavailable message; UI remains visible | Message displayed; UI remained visible | PASS |
| 8 | Print statement and loop | Script runs successfully | Expected output; backend returned 200 OK | PASS |

## 2. Plugin Manager Tests

| No. | Input / Action | Expected Result | Observed Result | Result |
|---|---|---|---|---|
| 9 | Save a plugin with a name | Plugin is saved and its ID is shown | Not tested yet | NOT TESTED |
| 10 | Save with an empty name | Friendly validation error | Not tested yet | NOT TESTED |
| 11 | Save two plugins with different names | Both appear in the plugin list | Not tested yet | NOT TESTED |
| 12 | Load a saved plugin | Its code appears in the editor | Not tested yet | NOT TESTED |
| 13 | Load an unknown plugin ID | Friendly error is displayed | Not tested yet | NOT TESTED |
| 14 | Refresh the plugin list | Saved mock plugins are listed accurately | Not tested yet | NOT TESTED |
| 15 | Remove a plugin | UI explains removal is local-only | Not tested yet | NOT TESTED |

## 3. Webhook Tests

| No. | Input / Action | Expected Result | Observed Result | Result |
|---|---|---|---|---|
| 16 | Trigger webhook without selecting a plugin | Clear message; no request is made | Not tested yet | NOT TESTED |
| 17 | Select a saved plugin and trigger webhook | Simulated result appears in Output | Not tested yet | NOT TESTED |
| 18 | Inspect simulated webhook output | Status and execution time display correctly; no `null ms` | Not tested yet | NOT TESTED |

## 4. Output and Error Handling Tests

| No. | Input / Action | Expected Result | Observed Result | Result |
|---|---|---|---|---|
| 19 | Successful execution response | Status displays Success | Not tested yet | NOT TESTED |
| 20 | Error execution response | Status displays Error | Not tested yet | NOT TESTED |
| 21 | Timeout response | Status displays Timed out | Not tested yet | NOT TESTED |
| 22 | HTTP 422 response | Friendly Invalid request message | Not tested yet | NOT TESTED |
| 23 | Empty stderr | Red error panel is hidden | Not tested yet | NOT TESTED |
| 24 | Missing execution time | No `null ms` is displayed | Not tested yet | NOT TESTED |

## 5. Testing Notes

- Tests 1–8 reflect previously recorded results.
- New tests must be performed before marking them PASS.
- Plugin Save, List, Load, and Webhook currently use mock mode.
- Real plugin and webhook integration is blocked until the backend API contract is documented and confirmed.
- Add screenshots of actual results to the frontend documentation.
-