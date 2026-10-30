#!/usr/bin/env python3
"""Board-side arm runner for the egui/Sidestep trials. Run as root on the board
with its system python3 (stdlib only), under the board lock, e.g.

    ssh k230 "$PY - --bin /nix/store/...-egui-software-probe/bin/egui-software-probe \
        --name egui --out /var/tmp/toolkit-eval/pair1-egui" < tools/toolkit-eval-board.py

It starts ONE client as the `shell` user in the normal Sway session, lets it
idle, then drives a sleep-paced scripted pointer workload through uinput
(tools/board-pointer.py, copied next to it as /var/tmp/toolkit-eval/board-pointer.py),
and writes a `qtquick-run/1`-shaped record plus the client's JSONL event log.
It never changes the session: the client is stopped by PID and the compositor
identity is compared before and after. Evidence class: injected board input.
"""
import argparse
import importlib.util
import json
import os
import signal
import subprocess
import sys
import time

TICK_US = 1_000_000 // os.sysconf("SC_CLK_TCK")
SHELL_ENV = ["XDG_RUNTIME_DIR=/run/shell", "WAYLAND_DISPLAY=wayland-1", "SWAYSOCK=/run/shell/sway-ipc.sock"]


def mono_ms():
    return int(time.clock_gettime(time.CLOCK_MONOTONIC) * 1000)


def cpu_us(pid):
    with open(f"/proc/{pid}/stat") as f:
        rest = f.read().rsplit(")", 1)[1].split()
    return (int(rest[11]) + int(rest[12])) * TICK_US  # utime + stime


def meminfo():
    out = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":")
            out[k] = int(v.split()[0])
    return out


def used_kib():
    m = meminfo()
    return m["MemTotal"] - m["MemAvailable"]


def smaps_rollup(pid):
    out = {}
    try:
        with open(f"/proc/{pid}/smaps_rollup") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[0].rstrip(":") in ("Rss", "Pss", "Pss_Anon", "Pss_File", "Private_Dirty"):
                    out[parts[0].rstrip(":")] = int(parts[1])
    except OSError:
        pass
    return out


def run_as_shell(*cmd, check=True, timeout=30):
    full = ["runuser", "-u", "shell", "--", "env", *SHELL_ENV, *cmd]
    return subprocess.run(full, capture_output=True, text=True, check=check, timeout=timeout)


def pid_of(exe_basename):
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/comm") as f:
                comm = f.read().strip()
            if comm == exe_basename[:15]:
                return int(name)
        except OSError:
            continue
    return None


def identity():
    sway = pid_of("sway")
    return {
        "sway_pid": sway,
        "sway_exe": os.readlink(f"/proc/{sway}/exe") if sway else None,
        "system": os.readlink("/run/current-system"),
        "boot_id": open("/proc/sys/kernel/random/boot_id").read().strip(),
        "cmdline_init": [a for a in open("/proc/cmdline").read().split() if a.startswith("init=")],
    }


def output_size():
    out = run_as_shell("swaymsg", "-t", "get_outputs", "-r").stdout
    rects = [o["rect"] for o in json.loads(out) if o.get("active")]
    w = max(r["x"] + r["width"] for r in rects)
    h = max(r["y"] + r["height"] for r in rects)
    return w, h


def load_pointer(path):
    spec = importlib.util.spec_from_file_location("board_pointer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Injector:
    """Sleep-paced uinput pointer. Never spins: every wait is time.sleep."""

    def __init__(self, mod, width, height):
        self.m, self.w, self.h = mod, width, height
        self.fd = mod.open_device(b"toolkit-eval pointer")
        time.sleep(0.8)
        self.interactions = []

    def move(self, x, y):
        m = self.m
        m.emit(self.fd, m.EV_ABS, m.ABS_X, round(x / max(self.w - 1, 1) * m.ABS_MAX))
        m.emit(self.fd, m.EV_ABS, m.ABS_Y, round(y / max(self.h - 1, 1) * m.ABS_MAX))
        m.syn(self.fd)

    def button(self, v):
        self.m.emit(self.fd, self.m.EV_KEY, self.m.BTN_LEFT, v)
        self.m.syn(self.fd)

    def tap(self, x, y, label):
        self.interactions.append({"kind": "press", "label": label, "t": mono_ms()})
        self.move(x, y)
        time.sleep(0.04)
        self.button(1)
        time.sleep(0.06)
        self.button(0)

    def swipe(self, x1, y1, x2, y2, ms, label):
        self.interactions.append({"kind": "press", "label": label, "t": mono_ms()})
        self.move(x1, y1)
        time.sleep(0.04)
        self.button(1)
        steps = max(int(ms / 16), 2)
        for i in range(1, steps + 1):
            time.sleep(ms / 1000 / steps)
            self.move(x1 + (x2 - x1) * i / steps, y1 + (y2 - y1) * i / steps)
        self.button(0)

    def close(self):
        time.sleep(0.2)
        import fcntl
        fcntl.ioctl(self.fd, self.m.UI_DEV_DESTROY)
        os.close(self.fd)


def workload(inj, seconds):
    """Scroll, row tap, mover tap and an interrupting second mover tap, repeated for `seconds`."""
    end = time.monotonic() + seconds
    cycle = 0
    while time.monotonic() < end:
        up = cycle % 2 == 0
        a, b = (620, 250) if up else (250, 620)
        inj.swipe(284, a, 284, b, 260, "scroll")
        time.sleep(0.25)
        inj.tap(284, 400, "row-tap")
        time.sleep(0.2)
        x = 96 if cycle % 2 == 0 else 460
        inj.tap(x, 840, "mover-tap")
        time.sleep(0.12)  # inside the 280 ms animation: an interrupting retarget
        inj.tap(460 if cycle % 2 == 0 else 96, 840, "mover-retarget")
        time.sleep(0.5)
        cycle += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--idle", type=float, default=30)
    ap.add_argument("--active", type=float, default=30)
    ap.add_argument("--deadline", type=float, default=150, help="hard cap in seconds for the whole arm")
    ap.add_argument("--pointer", default="/var/tmp/toolkit-eval/board-pointer.py")
    ap.add_argument("--grim", action="store_true")
    ap.add_argument("--extra", nargs="*", default=[])
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    os.chmod(args.out, 0o777)
    events_path = os.path.join(args.out, "events.jsonl")
    open(events_path, "w").close()
    os.chmod(events_path, 0o666)
    before_id = identity()
    width, height = output_size()
    run = {"schema": "toolkit-eval-run/1", "name": args.name, "binary": args.bin, "output": [width, height],
           "identity_before": before_id, "cpu_freq_khz": None}
    try:
        run["cpu_freq_khz"] = int(open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq").read())
    except OSError:
        pass
    deadline = time.monotonic() + args.deadline
    mem_before = used_kib()
    run["memory"] = {"before_kib": mem_before}
    launch = mono_ms()
    run["launch_mono_ms"] = launch
    shell_cmd = f"exec {args.bin} {' '.join(args.extra)} > {events_path} 2> {events_path}.err"
    proc = subprocess.Popen(["runuser", "-u", "shell", "--", "env", *SHELL_ENV, "sh", "-c", shell_cmd])
    client = None
    inj = None
    try:
        base = os.path.basename(args.bin)
        while time.monotonic() < deadline:
            client = pid_of(base)
            if client and '"first_frame"' in open(events_path).read():
                break
            time.sleep(0.05)
        else:
            raise RuntimeError("no first_frame before the deadline")
        sway = before_id["sway_pid"]
        run["client_pid"] = client
        time.sleep(1.0)  # settle
        # Idle phase.
        c0, s0, t0 = cpu_us(client), cpu_us(sway), time.monotonic()
        time.sleep(args.idle)
        c1, s1, t1 = cpu_us(client), cpu_us(sway), time.monotonic()
        idle = {"elapsed_s": t1 - t0, "client_cpu_us": c1 - c0, "sway_cpu_us": s1 - s0}
        run["smaps_idle"] = smaps_rollup(client)
        if args.grim:
            run_as_shell("grim", os.path.join(args.out, "idle.png"), check=False)
        # Active phase.
        mod = load_pointer(args.pointer)
        inj = Injector(mod, width, height)
        os.times()
        j0 = os.times()
        c0, s0, t0, m0 = cpu_us(client), cpu_us(sway), time.monotonic(), mono_ms()
        workload(inj, args.active)
        c1, s1, t1, m1 = cpu_us(client), cpu_us(sway), time.monotonic(), mono_ms()
        j1 = os.times()
        active = {"elapsed_s": t1 - t0, "client_cpu_us": c1 - c0, "sway_cpu_us": s1 - s0,
                  "start_mono_ms": m0, "end_mono_ms": m1}
        run["phases"] = {"idle": idle, "active": active}
        run["injector_cpu_s"] = (j1.user + j1.system) - (j0.user + j0.system)
        run["interactions"] = inj.interactions
        run["memory"]["active_used_kib"] = used_kib()
        run["smaps_active"] = smaps_rollup(client)
        if args.grim:
            run_as_shell("grim", os.path.join(args.out, "active.png"), check=False)
        run["ok"] = True
    except Exception as exc:  # recorded, not hidden
        run["ok"] = False
        run["error"] = repr(exc)
    finally:
        if inj:
            inj.close()
        for pid in {client, proc.pid}:
            if pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        left = pid_of(os.path.basename(args.bin))
        if left:
            try:
                os.kill(left, signal.SIGKILL)
            except OSError:
                pass
        run["client_gone"] = pid_of(os.path.basename(args.bin)) is None
        run["identity_after"] = identity()
        run["same_identity"] = {k: before_id[k] == run["identity_after"][k] for k in before_id}
    with open(os.path.join(args.out, "run.json"), "w") as f:
        json.dump(run, f, indent=1)
    print(json.dumps({k: run.get(k) for k in ("ok", "error", "client_gone", "same_identity")}))


if __name__ == "__main__":
    main()
