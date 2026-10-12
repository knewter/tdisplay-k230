#!/usr/bin/env python3
"""Run a standalone CPU0 payload on QEMU's `k230` machine and drive it.

QEMU proof only. This never touches the board. The machine models a single
C908 hart, no RMU/boot-vector release, and no CPU1; the image is placed with
`-device loader` and the hart's PC is set to its address. Guest memory is
read and written through QEMU's gdbstub (remote protocol m/M packets) and
inspected through QMP's human-monitor-command.

  small-core-qemu-probe.py heartbeat BIN [--base 0x7000000]
  small-core-qemu-probe.py echo BIN [--base 0x7000000]
"""
import argparse, json, os, socket, subprocess, sys, tempfile, time


class Qmp:
    def __init__(self, path):
        self.s = socket.socket(socket.AF_UNIX)
        self.s.connect(path)
        self.f = self.s.makefile("rw")
        self.f.readline()
        self.call("qmp_capabilities")

    def call(self, cmd, **args):
        self.f.write(json.dumps({"execute": cmd, "arguments": args}) + "\n")
        self.f.flush()
        while True:
            r = json.loads(self.f.readline())
            if "return" in r or "error" in r:
                return r

    def hmp(self, line):
        return self.call("human-monitor-command", **{"command-line": line}).get("return", "")


class Gdb:
    """Minimal gdb remote client. The stub only serves m/M while the VM is
    stopped, so every access is bracketed by halt()/resume()."""

    def __init__(self, path):
        self.s = socket.socket(socket.AF_UNIX)
        self.s.connect(path)
        self.s.settimeout(5)
        self.buf = b""
        self.running = False
        self.cmd("qSupported")

    def _packet(self):
        while True:
            i = self.buf.find(b"$")
            if i >= 0:
                j = self.buf.find(b"#", i)
                if j >= 0 and len(self.buf) >= j + 3:
                    pkt = self.buf[i + 1:j].decode()
                    self.buf = self.buf[j + 3:]
                    self.s.sendall(b"+")
                    return pkt
            self.buf += self.s.recv(65536)

    def _send(self, payload):
        self.s.sendall(b"$%s#%02x" % (payload.encode(), sum(payload.encode()) & 0xFF))

    def cmd(self, payload):
        self._send(payload)
        while True:
            r = self._packet()
            if r[:1] in ("T", "S", "O") and r != "OK" and payload[:1] not in ("q",):
                continue  # asynchronous stop/console notification
            return r

    def halt(self):
        if self.running:
            self.s.sendall(b"\x03")
            while True:
                r = self._packet()
                if r[:1] in ("T", "S"):
                    break
            self.running = False

    def resume(self):
        if not self.running:
            self._send("c")
            self.running = True

    def read(self, addr, n):
        self.halt()
        return bytes.fromhex(self.cmd("m%x,%x" % (addr, n)))

    def write(self, addr, data):
        self.halt()
        r = self.cmd("M%x,%x:%s" % (addr, len(data), data.hex()))
        assert r == "OK", r

    def u32(self, a):
        return int.from_bytes(self.read(a, 4), "little")

    def u64(self, a):
        return int.from_bytes(self.read(a, 8), "little")

    def w32(self, a, v):
        self.write(a, (v & 0xFFFFFFFF).to_bytes(4, "little"))


def say(*a):
    print(*a, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["heartbeat", "echo"])
    ap.add_argument("bin")
    ap.add_argument("--base", type=lambda x: int(x, 0), default=0x07000000)
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="k230q-")
    qmp, gdb = os.path.join(tmp, "qmp"), os.path.join(tmp, "gdb")
    argv = ["qemu-system-riscv64", "-M", "k230", "-bios", "none", "-display", "none",
            "-serial", "null", "-qmp", "unix:%s,server=on,wait=off" % qmp,
            "-gdb", "unix:%s,server=on,wait=off" % gdb,
            "-device", "loader,file=%s,addr=%#x,cpu-num=0" % (a.bin, a.base)]
    say("# command:", " ".join(argv[:1] + argv[1:7]), "... -device loader,file=%s,addr=%#x,cpu-num=0" % (os.path.basename(a.bin), a.base))
    p = subprocess.Popen(argv, stderr=subprocess.PIPE)
    ok = True
    try:
        for _ in range(100):
            if os.path.exists(qmp) and os.path.exists(gdb):
                break
            time.sleep(0.1)
        time.sleep(0.5)
        q, g = Qmp(qmp), Gdb(gdb)
        g.resume()
        time.sleep(0.3)
        say("# qemu version / cpus:")
        say(q.hmp("info version").strip())
        say(q.hmp("info cpus").strip())
        regs = q.hmp("info registers")
        for l in regs.splitlines():
            if l.split()[:1] and l.split()[0] in ("priv", "pc", "misa", "mhartid"):
                say("  " + l)
        say("# xp /8wx %#x (initial)" % (a.base + 0x2000))
        say(q.hmp("xp /8wx %#x" % (a.base + 0x2000)).strip())
        page = a.base + 0x2000
        if a.mode == "heartbeat":
            v = []
            for _ in range(3):
                g.resume()
                time.sleep(0.4)
                v.append(g.u64(page))
                say("counter @%#x = %d" % (page, v[-1]))
            ok = v[0] < v[1] < v[2]
            say("mhartid word = %#x, misa word = %#x" % (g.u64(page + 8), g.u64(page + 16)))
            say("RESULT:", "PASS counters strictly increase" if ok else "FAIL")
        else:
            g.resume()
            time.sleep(0.5)
            magic = g.u32(page + 0x58)
            say("magic = %#x (expect 0x4f484345), mhartid = %d, misa = %#x" % (magic, g.u64(page + 0x48), g.u64(page + 0x50)))
            ok = magic == 0x4F484345
            hb = [g.u64(page + 0x40)]
            reqs = [(1, 0x11111111), (2, 0xDEADBEEF), (3, 0xFFFFFFFF), (9, 0x00000000), (4, 0x12345678)]
            for seq, val in reqs:
                g.w32(page + 4, val)
                g.w32(page + 0, seq)
                g.resume()
                line = page + 0x100 + 0x40 * (seq & 7)
                t0 = time.time()
                while time.time() - t0 < 3:
                    time.sleep(0.02)
                    if g.u32(line) == seq:
                        break
                    g.resume()
                dt = time.time() - t0
                rs, rv, ri, rn = (g.u32(line + i) for i in (0, 4, 8, 12))
                good = rs == seq and rv == (val + 1) & 0xFFFFFFFF and ri == (~val) & 0xFFFFFFFF
                ok &= good
                say("req seq=%d value=%#010x -> rsp_seq=%d value=%#010x inv=%#010x served=%d  (%.3fs poll) %s"
                    % (seq, val, rs, rv, ri, rn, dt, "ok" if good else "WRONG"))
            # a repeated seq with a new value must not be answered again
            served = g.u32(page + 0x5C)
            g.w32(page + 4, 0x55555555)
            g.w32(page + 0, 4)
            g.resume()
            time.sleep(0.3)
            same = g.u32(page + 0x5C) == served
            ok &= same
            say("re-sent seq=4 with new value: served stays %d -> %s" % (served, "ignored (ok)" if same else "ANSWERED (unexpected)"))
            hb.append(g.u64(page + 0x40))
            say("heartbeat words: %s" % hb)
            say("# xp: request line, then status line")
            say(q.hmp("xp /8wx %#x" % page).strip())
            say(q.hmp("xp /8wx %#x" % (page + 0x40)).strip())
            say("RESULT:", "PASS" if ok else "FAIL")
    finally:
        p.kill()
        p.wait()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
