# WasmBox Sandbox - Test Sheet

| No. | What I typed | What I expected | What I saw | Result |
|---|---|---|---|---|
| 1 | `print("hi")` | Output: hi | Output displayed | PASS |
| 2 | Two print statements | Both lines displayed | Both lines displayed | PASS |
| 3 | `print("hi"` | Syntax error | Syntax error displayed | PASS |
| 4 | `1/0` | Division-by-zero error | Error displayed | PASS |
| 5 | Empty code | Ask for Python code | Prompt displayed | PASS |
| 6 | `for i in range(3): print(i)` | Output: 0, 1, 2 | Output displayed | PASS |