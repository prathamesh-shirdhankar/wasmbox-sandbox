# ATTACK 3: run forever and hog the CPU.
# Safe result: the sandbox stops it after about 50 ms (status "timeout").
# Never run this with plain "python". It will freeze your terminal.
while True:
    pass