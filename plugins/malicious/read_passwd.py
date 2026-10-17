# ATTACK 1: try to read a secret file from the host machine.
# Safe result: the sandbox blocks it and the file contents never reach stdout.
# Never run this with plain "python". It is only for the WasmBox sandbox.
print(open("/etc/passwd").read())