# ATTACK 2: try to open a network connection to an outside IP address.
# Safe result: the sandbox blocks it, and "connected" is never printed.
# Never run this with plain "python". It is only for the WasmBox sandbox.
import socket

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
s.connect(("1.1.1.1", 80))
print("connected")