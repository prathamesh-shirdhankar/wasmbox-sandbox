# WasmBox Frontend Test Sheet

## Test Environment
- Frontend: React + Vite
- Backend: FastAPI
- Browser: Chrome
- Backend URL: http://localhost:8000

## Test Results

| No. | Test Case | Expected Result | Actual Result | Status |
|---|---|---|---|---|
| 1 | Successful Python execution | Python code executes and displays output | Both Hello messages displayed successfully | PASS |
| 2 | Invalid Python code | Error appears in stderr | ZeroDivisionError displayed correctly | PASS |
| 3 | Timeout handling | Execution stops after timeout | Timed out status displayed | PASS |
| 4 | Save Plugin | Plugin is saved successfully | Sashmita_Test saved with ID 4 | PASS |
| 5 | Refresh Plugin List | Saved plugins appear after refresh | All 4 plugins displayed | PASS |
| 6 | Load Plugin | Saved code loads into editor | Saved code loaded and executed successfully | PASS |
| 7 | Webhook execution | Webhook triggers successfully | Success status and output displayed | PASS |
| 8 | API error handling | Friendly error appears when backend is unavailable | Backend connection error displayed without application crash | PASS |

## Overall Result

- Total test cases: 8
- Passed: 8
- Failed: 0

All eight test cases were verified locally.