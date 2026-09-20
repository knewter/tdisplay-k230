import sys, time, serial

port = sys.argv[1]
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
poke = len(sys.argv) > 3 and sys.argv[3] == 'poke'

s = serial.Serial()
s.port = port; s.baudrate = baud; s.timeout = 0.2
s.rts = False; s.dtr = False
s.open()
time.sleep(0.2)
s.reset_input_buffer()

def drain(sec, tag):
    buf = b''
    end = time.time() + sec
    while time.time() < end:
        buf += s.read(4096)
    print(f"--- {tag} ({len(buf)} bytes) ---")
    if buf:
        sys.stdout.write(repr(buf)[2:-1].replace('\\r\\n', '\n').replace('\\n', '\n'))
        print()
    return buf

drain(2.0, f"{port} @ {baud} passive")
if poke:
    s.write(b'\r\n'); s.flush()
    drain(2.0, f"{port} @ {baud} after CR/LF")
s.close()
