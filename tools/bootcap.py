import sys, time, serial
port, dur = sys.argv[1], float(sys.argv[2])
s = serial.Serial(port, 115200, timeout=0.2)
time.sleep(0.3); s.reset_input_buffer()
s.write(b'\r\n'); s.flush(); time.sleep(0.5); s.reset_input_buffer()
print(">>> sending reboot", flush=True)
s.write(b'reboot\r\n'); s.flush()
buf = b''
end = time.time() + dur
while time.time() < end:
    buf += s.read(4096)
s.close()
sys.stdout.write(buf.decode('utf-8','replace'))
