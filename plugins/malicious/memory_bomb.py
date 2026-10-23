# ATTACK 4: grab far more memory than allowed (limit is about 10 MB).
# Safe result: the sandbox stops it (status "memory_exceeded").
# Capped at 200 MB so an accidental run on a laptop will not crash it.
# Never run this with plain "python". It is only for the WasmBox sandbox.
chunks = []
for _ in range(200):
    chunks.append(bytearray(1024 * 1024))  # 1 MB each
print("allocated", len(chunks), "MB")