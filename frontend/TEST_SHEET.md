WasmBox Sandbox — Test Sheet

1. Python Code Runner Tests

No.| Input / Action| Expected Result| Observed Result| Result
1| "print("hi")"| Output: hi| Output displayed| PASS (previously recorded)
2| Two print statements| Both lines displayed| Both lines displayed| PASS (previously recorded)
3| Invalid Python syntax| Syntax error displayed| Syntax error displayed| PASS (previously recorded)
4| "1/0"| Division-by-zero error| Error displayed| PASS (previously recorded)
5| Empty code| Friendly validation message| Prompt displayed| PASS (previously recorded)
6| Loop printing 0–2| Output: 0, 1, 2| Output displayed| PASS (previously recorded)
7| Stop backend and run code| Friendly server-unavailable message; UI remains visible| Message displayed; UI remained visible| PASS (previously recorded)
8| Print statement and loop| Script runs successfully| Backend previously returned HTTP 200| PASS (previously recorded)

2. Plugin Manager Tests

No.| Input / Action| Expected Result| Observed Result| Result
9| Save a plugin with a name| Plugin is saved and its ID is shown| Saved "FrontendTest" (ID 1) and "FrontendTest2" (ID 2)| PASS (mock mode)
10| Save with an empty name| Friendly validation error| Not tested yet| NOT TESTED
11| Save two plugins with different names| Both appear in the plugin list| Two plugins appeared in the list| PASS (mock mode)
12| Load a saved plugin| Success message; saved code loads into editor| Loaded "FrontendTest" message observed| PASS (mock mode)
13| Load an unknown plugin ID| Friendly error is displayed| Not tested yet| NOT TESTED
14| Refresh the plugin list| Saved mock plugins are listed accurately| Not tested separately| NOT TESTED
15| Remove a plugin| UI behavior matches the implemented design| Remove behavior not tested| NOT TESTED

3. Webhook Tests

No.| Input / Action| Expected Result| Observed Result| Result
16| Trigger webhook for a selected plugin| Simulated webhook completes successfully| "Webhook completed" displayed| PASS (mock mode)
17| Trigger webhook without selecting a plugin| Friendly guidance or validation message| Not tested yet| NOT TESTED
18| Trigger webhook and inspect output| Output clearly identifies simulated webhook execution| "Mock webhook completed for FrontendTest." displayed| PASS (mock mode)

4. Output and Error Handling Tests

No.| Input / Action| Expected Result| Observed Result| Result
19| Preview Success| Success status and output displayed| Demo completed successfully; 125 ms displayed| PASS (mock preview)
20| Preview Error| Error status and message displayed| Error status and demo message displayed; 125 ms shown| PASS (mock preview)
21| Preview Timed out| Timeout status and message displayed| Timeout demo preview displayed; 1500 ms shown| PASS (mock preview)
22| Execution time is null| No misleading "null ms" displayed| Not tested separately| NOT TESTED
23| Backend unavailable during Run| Friendly error; UI remains usable| Previously recorded in Test 7| PASS (previously recorded)
24| Run Python against the current backend| Actual response and output displayed correctly| Must verify against the current code| NOT TESTED

5. Build and Documentation Checks

No.| Input / Action| Expected Result| Observed Result| Result
25| Run "npm run build"| Build completes without errors| Build previously completed successfully| PASS (previously recorded)
26| Review frontend README| Setup, usage, and mock limitations documented| Must verify final README| NOT TESTED
27| Review screenshots| Screenshots are present and accurately labelled| Must verify screenshot files| NOT TESTED
28| Review changes with "git diff --check"| No whitespace errors| Not tested yet| NOT TESTED

Testing Notes

- Previously recorded Python runner results are retained as historical results; they have not all been rerun against the current implementation.
- Plugin Manager and Webhook results marked mock mode use simulated frontend data. They do not prove real backend integration.
- Demo status previews display Success, Error, and Timed out states; they do not execute Python.
- Real Run functionality must be checked against the existing backend separately.
- No plugin or webhook API contract should be assumed unless the backend team confirms it.
- Only mark a test PASS after observing the stated result. Record failures and unexpected behavior accurately.