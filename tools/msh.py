#!/usr/bin/env python3
"""Send command(s) to the RT-Thread msh console and print the reply."""
import sys, time, serial

port = "/dev/ttyACM0"
baud = 115200
args = sys.argv[1:]
if args and args[0].startswith('/dev/'):
    port = args.pop(0)
wait = 2.0
if args and args[0].startswith('--wait='):
    wait = float(args.pop(0).split('=')[1])
cmds = args

s = serial.Serial(port, baud, timeout=0.2)
time.sleep(0.3)
s.reset_input_buffer()

def read(sec):
    buf = b''
    end = time.time() + sec
    while time.time() < end:
        chunk = s.read(4096)
        if chunk:
            buf += chunk
            end = max(end, time.time() + 0.4)   # extend while data flows
    return buf

def show(b):
    t = b.decode('utf-8', 'replace')
    for line in t.splitlines():
        print(line)

s.write(b'\r\n'); s.flush(); read(0.6)   # settle prompt

for c in cmds:
    print(f"\n===== msh> {c} =====")
    s.write(c.encode() + b'\r\n'); s.flush()
    show(read(wait))
s.close()
