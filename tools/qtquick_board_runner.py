#!/usr/bin/env python3
"""Deadline-controlled runner for transient Qt Quick / baseline clients.

Runs ON the board as root (stdlib only), by the host controller in
tools/qtquick_board.py, while the operator holds the board lock. It is a
client of the normal Sway session: it never stops `shell`, never touches boot
selection and never leaves a unit behind.

  runner.py arm --spec SPEC.json      one measured run (idle, active, functional)
  runner.py identity --spec SPEC.json short run with WAYLAND_DEBUG protocol identity
  runner.py restore --id ID           independent restoration (also run by the guard timer)
  runner.py verify --id ID            read-only check that the normal session is back

Bounded lifetime has three independent layers: the client's own
--exit-after-ms, the unit's RuntimeMaxSec (systemd kills the cgroup if this
controller or the SSH link dies), and a transient guard timer that runs
`restore` after the deadline even if this process was SIGKILLed.
Evidence classes: board, injected touch (uinput), native grim capture. Never
glass.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

STATE_DIR = Path("/var/tmp/qtq")
SWAYSOCK = "/run/shell/sway-ipc.sock"
OUTPUT_W, OUTPUT_H = 1232, 568           # logical landscape output (DSI-1, transform 270)
RAW_W, RAW_H = 2400, 1080                # held-frame raw ranges, as touch-trackpad emits
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{3,40}$")
BIN_RE = re.compile(r"^/nix/store/[0-9a-z]{32}-[A-Za-z0-9+._-]+/bin/[A-Za-z0-9._-]+$")
OSK_FLAG = "/run/shell/k230-keyboard-visible"


class System:
    """All side effects. Tests substitute a fake."""
    def __init__(self):
        self.python = sys.executable

    def run(self, argv, timeout=30, check=False):
        try:
            res = subprocess.run(argv, text=True, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return 124, ""
        if check and res.returncode:
            raise RuntimeError(f"{argv[0]} exited {res.returncode}: {res.stderr.strip()[:200]}")
        return res.returncode, res.stdout

    def shell_env(self, argv):
        return ["runuser", "-u", "shell", "--", "env", f"SWAYSOCK={SWAYSOCK}", "WAYLAND_DISPLAY=wayland-1",
                "XDG_RUNTIME_DIR=/run/shell"] + argv

    def read(self, path, default=None):
        try:
            return Path(path).read_text()
        except OSError:
            return default

    def write(self, path, text):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(text)

    def exists(self, path):
        return Path(path).exists()

    def sleep(self, seconds):
        time.sleep(max(0.0, seconds))

    def mono(self):
        return time.monotonic()

    def cpu_seconds(self):
        t = os.times()
        return t.user + t.system

    def tick_hz(self):
        return os.sysconf("SC_CLK_TCK")


# ---- scene geometry the scripted interactions aim at (client coordinates) ----
def plan_actions(viewport=(OUTPUT_W, OUTPUT_H)):
    """One cycle of interaction types. Coordinates are client-space; the
    runner offsets them by the window origin. Matches scene.h/Probe.qml."""
    return [
        ("drag", (300, 400, 300, 150, 220)),   # scroll the list up
        ("tap", (300, 250)),                    # a row
        ("drag", (300, 150, 300, 420, 220)),   # scroll back
        ("tap", (700, 250)),                    # mover: starts the animation
        ("tap", (700, 250)),                    # retarget while moving? re-hit after the pause below
        ("drag", (300, 420, 300, 130, 160)),   # fast flick
        ("tap", (300, 140)),                    # tap during the fling
    ]


class Touch:
    """Distinctly named uinput touch device in the held frame (like touch-trackpad's output)."""
    NAME = b"qtq trial injected touch"

    def __init__(self, system):
        import fcntl
        import struct
        self.system, self.fcntl, self.struct = system, fcntl, struct
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
        for bit in (EV_SYN, EV_KEY, EV_ABS):
            fcntl.ioctl(self.fd, 0x40045564, bit)
        fcntl.ioctl(self.fd, 0x40045565, 0x14a)
        axes = [0, 1, 0x2f, 0x39, 0x35, 0x36]
        for a in axes:
            fcntl.ioctl(self.fd, 0x40045567, a)
        fcntl.ioctl(self.fd, 0x4004556e, 1)  # INPUT_PROP_DIRECT
        mx, mn = [0] * 64, [0] * 64
        mx[0] = mx[0x35] = RAW_W - 1
        mx[1] = mx[0x36] = RAW_H - 1
        mx[0x2f] = 9
        mx[0x39] = 65535
        dev = struct.pack("80sHHHHi", self.NAME, 0x18, 0, 0, 0, 0)
        dev += struct.pack("64i", *mx) + struct.pack("64i", *mn) + struct.pack("64i", *[0] * 64) * 2
        os.write(self.fd, dev)
        fcntl.ioctl(self.fd, 0x5501)
        self.tid = 200
        system.sleep(1.0)  # the compositor adds the device

    def _emit(self, t, c, v):
        now = time.time()
        sec = int(now)
        os.write(self.fd, self.struct.pack("llHHi", sec, int((now - sec) * 1e6), t, c, v))

    def _pos(self, x, y):
        rx = min(RAW_W - 1, max(0, round(x * (RAW_W - 1) / (OUTPUT_W - 1))))
        ry = min(RAW_H - 1, max(0, round(y * (RAW_H - 1) / (OUTPUT_H - 1))))
        self._emit(3, 0x35, rx)
        self._emit(3, 0x36, ry)
        self._emit(3, 0, rx)
        self._emit(3, 1, ry)
        self._emit(0, 0, 0)

    def down(self, x, y):
        self.tid += 1
        self._emit(3, 0x2f, 0)
        self._emit(3, 0x39, self.tid)
        self._emit(1, 0x14a, 1)
        self._pos(x, y)

    def move(self, x, y):
        self._emit(3, 0x2f, 0)
        self._pos(x, y)

    def up(self):
        self._emit(3, 0x2f, 0)
        self._emit(3, 0x39, -1)
        self._emit(1, 0x14a, 0)
        self._emit(0, 0, 0)

    def tap(self, x, y, hold_s=0.06):
        self.down(x, y)
        self.system.sleep(hold_s)
        self.up()

    def drag(self, x0, y0, x1, y1, ms):
        """Sleep-paced (never a busy-wait: one online CPU)."""
        steps = max(4, int(ms / 16))
        t0 = self.system.mono()
        self.down(x0, y0)
        for i in range(1, steps + 1):
            self.system.sleep(t0 + (ms / 1000.0) * i / steps - self.system.mono())
            self.move(x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps)
        self.up()

    def close(self):
        try:
            self.fcntl.ioctl(self.fd, 0x5502)
        finally:
            os.close(self.fd)


class Arm:
    def __init__(self, system, spec, touch_factory=None):
        if not ID_RE.match(spec["id"]):
            raise ValueError("bad run id")
        if not BIN_RE.match(spec["binary"]):
            raise ValueError("binary must be a Nix store executable")
        self.s, self.spec = system, spec
        self.id = spec["id"]
        self.unit = f"qtq-{self.id}.service"
        self.guard = f"qtq-guard-{self.id}"
        self.dir = STATE_DIR / self.id
        self.touch_factory = touch_factory or (lambda: Touch(system))
        self.touch = None
        self.pre = None
        self.record = {"schema": "qtquick-run/1", "id": self.id, "toolkit": spec["toolkit"],
                       "pair": spec.get("pair"), "order": spec.get("order"),
                       "manifest_hash": spec.get("manifest_hash"), "artifact": spec.get("artifact"),
                       "boundary": "client_commit", "evidence_class": "board; injected uinput touch; native grim capture",
                       "phases": {}, "interactions": [], "functional": {}, "captures": [], "log": []}

    # -- helpers --
    def log(self, message):
        self.record["log"].append(f"{self.s.mono():.3f} {message}")

    def swaymsg(self, *args):
        rc, out = self.s.run(self.s.shell_env(["swaymsg", "-r"] + list(args)), timeout=15)
        return json.loads(out) if rc == 0 and out.strip() else None

    def tree_windows(self):
        tree = self.swaymsg("-t", "get_tree")
        found = []

        def walk(node, focus_path):
            if node.get("app_id") or node.get("window"):
                found.append(node)
            for child in node.get("nodes", []) + node.get("floating_nodes", []):
                walk(child, focus_path)
        if tree:
            walk(tree, [])
        return found

    def snapshot(self):
        wins = self.tree_windows()
        focused = next((w for w in wins if w.get("focused")), None)
        sway_pid = self.s.run(["pgrep", "-x", "sway"])[1].split()
        return {"sway_pid": sway_pid[0] if sway_pid else None,
                "windows": sorted(w.get("app_id") or "?" for w in wins),
                "focused_app_id": focused.get("app_id") if focused else None,
                "focused_con": focused.get("id") if focused else None,
                "shell_active": self.s.run(["systemctl", "is-active", "shell"])[1].strip() == "active",
                "qtq_units": [u for u in self.s.run(["systemctl", "list-units", "--all", "--plain", "--no-legend",
                                                      "qtq-*"])[1].split("\n") if u.strip()]}

    def meminfo_used_kib(self):
        text = self.s.read("/proc/meminfo", "")
        total = re.search(r"MemTotal:\s+(\d+)", text)
        avail = re.search(r"MemAvailable:\s+(\d+)", text)
        return int(total.group(1)) - int(avail.group(1)) if total and avail else None

    def sway_ticks(self, pid):
        text = self.s.read(f"/proc/{pid}/stat", "")
        if not text:
            return None
        fields = text[text.rindex(")") + 2:].split()
        return int(fields[11]) + int(fields[12])

    def unit_cpu_us(self):
        text = self.s.read(f"/sys/fs/cgroup/system.slice/{self.unit}/cpu.stat", "")
        m = re.search(r"usage_usec (\d+)", text)
        return int(m.group(1)) if m else None

    def thermal(self):
        out = {}
        for i in range(3):
            v = self.s.read(f"/sys/class/thermal/thermal_zone{i}/temp")
            if v:
                out[f"zone{i}_mC"] = int(v.strip())
        return out

    def find_window(self):
        app = self.spec["app_id"]
        for w in self.tree_windows():
            if w.get("app_id") == app or w.get("name") == app:
                r = w["rect"]
                return {"x": r["x"], "y": r["y"], "w": r["width"], "h": r["height"], "id": w.get("id"),
                        "floating": w.get("type") == "floating_con", "focused": bool(w.get("focused"))}
        return None

    def capture(self, name):
        path = self.dir / f"{name}.png"
        rc, _ = self.s.run(self.s.shell_env(["grim", "-o", "DSI-1", str(path)]), timeout=90)
        ok = rc == 0 and self.s.exists(path)
        self.record["captures"].append({"name": name, "file": f"{name}.png" if ok else None,
                                        "window": self.find_window(), "mono_s": round(self.s.mono(), 3),
                                        "osk_visible": self.s.exists(OSK_FLAG)})
        return ok

    def events_text(self):
        return self.s.read(self.dir / "client.jsonl", "")

    def first_frame_seen(self):
        return '"first_frame"' in self.events_text()

    # -- lifecycle --
    def arm_guard(self):
        deadline = int(self.spec["deadline_s"]) + 25
        rc, _ = self.s.run(["systemd-run", f"--unit={self.guard}", f"--on-active={deadline}s", "--collect",
                            self.s.python, str(Path(__file__).resolve()), "restore", "--id", self.id,
                            "--reason", "guard-deadline"])
        if rc:
            raise RuntimeError("could not arm the independent guard timer")

    def launch(self):
        exit_ms = int(self.spec["exit_after_s"] * 1000)
        env = [f"--setenv=WAYLAND_DISPLAY=wayland-1", f"--setenv=XDG_RUNTIME_DIR=/run/shell"]
        for key, value in self.spec.get("env", {}).items():
            env.append(f"--setenv={key}={value}")
        argv = ["systemd-run", f"--unit={self.unit}", "--uid=shell", "--collect", "--quiet",
                f"--property=RuntimeMaxSec={int(self.spec['deadline_s'])}", "--property=CPUAccounting=yes",
                "--property=MemoryAccounting=yes", f"--property=StandardOutput=file:{self.dir}/client.jsonl",
                f"--property=StandardError=file:{self.dir}/client.err"] + env + \
               [self.spec["binary"], "--exit-after-ms", str(exit_ms)] + self.spec.get("args", [])
        self.record["launch_mono_ms"] = int(self.s.mono() * 1000)
        rc, out = self.s.run(argv)
        if rc:
            raise RuntimeError("client launch failed")
        self.log("launched")

    def wait_first_frame(self, timeout_s):
        end = self.s.mono() + timeout_s
        while self.s.mono() < end:
            if self.first_frame_seen():
                return True
            if self.s.run(["systemctl", "is-active", self.unit])[1].strip() not in ("active", "activating"):
                return False
            self.s.sleep(0.25)
        return False

    def stop_client(self):
        self.s.run(["systemctl", "stop", self.unit], timeout=20)
        self.s.run(["systemctl", "reset-failed", self.unit], timeout=10)

    def restore(self, reason):
        """Idempotent. Removes only this run's unit and window, then refocuses."""
        res = {"ok": False, "reason": reason, "id": self.id, "actions": []}
        self.stop_client()
        res["actions"].append("unit-stopped")
        self.s.run(["systemctl", "stop", f"{self.guard}.timer"], timeout=10)
        self.s.run(["systemctl", "reset-failed", f"{self.guard}.service"], timeout=10)
        app = self.spec["app_id"]
        if any(w.get("app_id") == app for w in self.tree_windows()):
            self.swaymsg(f'[app_id="^{re.escape(app)}$"]', "kill")
            self.s.sleep(1.0)
            res["actions"].append("window-killed")
        pre = self.pre or json.loads(self.s.read(self.dir / "pre.json", "null") or "null")
        if pre and pre.get("focused_con"):
            now = self.snapshot()
            if now["focused_app_id"] != pre["focused_app_id"] and pre["focused_app_id"] in now["windows"]:
                self.swaymsg(f'[con_id={int(pre["focused_con"])}]', "focus")
                res["actions"].append("refocused")
                self.s.sleep(0.5)
        post = self.snapshot()
        res["post"] = post
        ok = post["shell_active"] and all(self.id not in u for u in post["qtq_units"]) \
            and app not in post["windows"] and post["focused_app_id"] != app
        if pre:
            # Other agents may open/close their own windows meanwhile; the compositor and the
            # shell must be the same, and focus must be back on the previous window when it still exists.
            ok = ok and post["sway_pid"] == pre["sway_pid"]
            res["focus_same_as_before"] = post["focused_app_id"] == pre["focused_app_id"]
            if pre["focused_app_id"] in post["windows"]:
                ok = ok and res["focus_same_as_before"]
        res["ok"] = bool(ok)
        return res

    # -- phases --
    def run_phase(self, name, seconds, pid, active_fn=None):
        c0, s0, t0 = self.unit_cpu_us(), self.sway_ticks(pid), self.s.mono()
        u0 = self.s.cpu_seconds()
        mem = [self.meminfo_used_kib()]
        start_ms = int(t0 * 1000)
        therm0 = self.thermal()
        if active_fn:
            active_fn(t0 + seconds, mem)
        while self.s.mono() < t0 + seconds:
            self.s.sleep(min(5.0, t0 + seconds - self.s.mono()))
            mem.append(self.meminfo_used_kib())
        t1 = self.s.mono()
        c1, s1 = self.unit_cpu_us(), self.sway_ticks(pid)
        hz = self.s.tick_hz()
        self.record["phases"][name] = {
            "elapsed_s": round(t1 - t0, 3),
            "client_cpu_us": None if c0 is None or c1 is None else c1 - c0,
            "sway_cpu_us": None if s0 is None or s1 is None else int((s1 - s0) * 1e6 / hz),
            "start_mono_ms": start_ms, "end_mono_ms": int(t1 * 1000),
            "mem_used_kib_samples": [m for m in mem if m is not None],
            "runner_cpu_s": round(self.s.cpu_seconds() - u0, 3),
            "thermal_start": therm0, "thermal_end": self.thermal(),
        }

    def interact(self, win):
        """Scripted interactions for the active phase; sleep-paced, counted."""
        ox, oy = win["x"], win["y"]
        cycle = plan_actions()

        def active(deadline, mem):
            i = 0
            next_mem = self.s.mono() + 5
            while self.s.mono() < deadline - 1.2:
                kind, args = cycle[i % len(cycle)]
                t = self.s.mono()
                if kind == "drag":
                    x0, y0, x1, y1, ms = args
                    self.touch.drag(ox + x0, oy + y0, ox + x1, oy + y1, ms)
                else:
                    self.touch.tap(ox + args[0], oy + args[1])
                self.record["interactions"].append({"kind": kind, "mono_ms": int(t * 1000)})
                i += 1
                # a short gap after a mover tap so the second tap lands mid-animation
                self.s.sleep(0.12 if (i % len(cycle)) == 5 else 0.55)
                if self.s.mono() >= next_mem:
                    mem.append(self.meminfo_used_kib())
                    next_mem += 5
        return active

    def functional(self, win):
        """Captured checks after the measured phases. Gates are decided host-side from the PNGs."""
        ox, oy = win["x"], win["y"]
        t = self.touch
        self.capture("f0-initial")
        t.tap(ox + 300, oy + 130)           # row 0: only it changes colour when selected
        self.s.sleep(0.6)
        self.capture("f1-after-row-tap")
        t.drag(ox + 300, oy + 420, ox + 300, oy + 120, 300)
        self.s.sleep(1.8)
        self.capture("f2-after-scroll")
        t.tap(ox + 700, oy + 250)           # mover: first tap starts the animation toward the right
        self.s.sleep(0.10)
        t.tap(ox + 1000, oy + 250)          # second tap lands on the moving rect: it must retarget back
        self.s.sleep(0.9)
        self.capture("f3-after-interrupt")
        t.tap(ox + 800, oy + 130)           # text field focus
        self.s.sleep(2.0)
        self.record["functional_raw"] = {"osk_visible_after_focus": self.s.exists(OSK_FLAG),
                                         "text_input_enable_logged": '"text_input_enable"' in self.events_text()}
        self.capture("f4-field-focused")
        # wvkbd-mobintl: bottom 240 px, first row 'q w e ...' evenly spread.
        for kx in (62, 185):
            t.tap(kx, OUTPUT_H - 240 + 30)
            self.s.sleep(0.5)
        self.s.sleep(0.8)
        self.capture("f5-after-keys")

    def run(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.chown(self.dir, user="shell")  # the client writes its JSONL here as `shell`
        except (LookupError, PermissionError, OSError):
            pass
        self.pre = self.snapshot()
        self.s.write(self.dir / "pre.json", json.dumps(self.pre))
        self.record["pre"] = self.pre
        self.record["boot_id"] = (self.s.read("/proc/sys/kernel/random/boot_id", "") or "").strip()
        self.record["uptime_s"] = float((self.s.read("/proc/uptime", "0 0").split() or ["0"])[0])
        self.record["memory"] = {"before_kib": self.meminfo_used_kib()}
        self.record["system"] = os.path.realpath("/run/current-system")
        status = "ok"
        try:
            self.arm_guard()
            self.launch()
            if not self.wait_first_frame(self.spec.get("startup_timeout_s", 30)):
                status = "no-first-frame"
                raise RuntimeError("no first frame before the startup timeout")
            self.s.sleep(2.0)
            win = self.find_window()
            self.record["window"] = win
            if not win:
                status = "no-window"
                raise RuntimeError("client window not found in the compositor tree")
            self.touch = self.touch_factory()
            self.capture("a0-startup")
            if self.spec.get("mode") == "negative":
                self.s.sleep(3.0)
                err = self.s.read(self.dir / "client.err", "") or ""
                self.record["negative_control"] = {"stderr_lines": [l.strip()[:200] for l in err.splitlines()
                                                                    if re.search(r"shader|effect|software|unsupported", l, re.I)][:10]}
                self.capture("n0-negative-control")
                self.stop_client()
                self.record["functional"]["bounded_lifetime"] = True
                return self.record
            pid = self.pre["sway_pid"]
            self.run_phase("idle", self.spec["idle_s"], pid)
            self.run_phase("active", self.spec["active_s"], pid, self.interact(win))
            self.record["injector_cpu_s"] = self.record["phases"]["active"]["runner_cpu_s"]
            mem = self.record["phases"]["active"]["mem_used_kib_samples"]
            self.record["memory"]["active_used_kib"] = max(mem) if mem else None
            self.record["memory"]["idle_used_kib"] = (self.record["phases"]["idle"]["mem_used_kib_samples"] or [None])[-1]
            self.functional(win)
            # allow the client's own exit-after-ms to end it
            end = self.s.mono() + self.spec["exit_after_s"] - (self.s.mono() - self.record["launch_mono_ms"] / 1000.0) + 10
            while self.s.mono() < end and self.s.run(["systemctl", "is-active", self.unit])[1].strip() in ("active", "activating"):
                self.s.sleep(1.0)
            alive = self.s.run(["systemctl", "is-active", self.unit])[1].strip() in ("active", "activating")
            self.record["functional"]["bounded_lifetime"] = not alive
        except BaseException as exc:  # includes SIGTERM/SIGINT converted by the caller
            self.record["error"] = f"{type(exc).__name__}: {exc}"[:300]
            if status == "ok":
                status = "error"
            raise
        finally:
            self.record["status"] = status
            try:
                if self.touch:
                    self.touch.close()
            except Exception as exc:  # noqa: BLE001
                self.log(f"touch close: {exc}")
            restoration = self.restore("arm-finally")
            self.record["restoration"] = restoration
            self.record["functional"]["restored"] = restoration["ok"]
            self.record["events_file"] = "client.jsonl"
            self.s.write(self.dir / "run.json", json.dumps(self.record, indent=1))
        return self.record


def install_signal_handlers():
    def bail(signum, frame):
        raise KeyboardInterrupt(f"signal {signum}")
    for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(sig, bail)


def cmd_restore(args, system=None):
    system = system or System()
    spec_path = STATE_DIR / args.id / "spec.json"
    spec = json.loads(system.read(spec_path, "null") or "null")
    if not spec:
        print(json.dumps({"ok": False, "reason": "no spec for run"}))
        return 1
    arm = Arm(system, spec)
    res = arm.restore(args.reason)
    system.write(STATE_DIR / args.id / "restore.json", json.dumps(res, indent=1))
    print(json.dumps(res))
    return 0 if res["ok"] else 1


def cmd_arm(args, system=None):
    system = system or System()
    spec = json.loads(Path(args.spec).read_text())
    arm = Arm(system, spec)
    system.write(STATE_DIR / spec["id"] / "spec.json", json.dumps(spec))
    install_signal_handlers()
    try:
        record = arm.run()
    except BaseException:
        print(json.dumps({"ok": False, "status": arm.record.get("status"), "error": arm.record.get("error"),
                          "restored": arm.record.get("functional", {}).get("restored")}))
        return 1
    print(json.dumps({"ok": True, "status": record["status"], "restored": record["functional"]["restored"]}))
    return 0


def cmd_identity(args, system=None):
    """Short run that records the Wayland protocol identity of the client."""
    system = system or System()
    spec = json.loads(Path(args.spec).read_text())
    arm = Arm(system, spec)
    system.write(STATE_DIR / spec["id"] / "spec.json", json.dumps(spec))
    install_signal_handlers()
    arm.dir.mkdir(parents=True, exist_ok=True)
    arm.pre = arm.snapshot()
    system.write(arm.dir / "pre.json", json.dumps(arm.pre))
    spec["env"] = dict(spec.get("env", {}), WAYLAND_DEBUG="client")
    ident = {"id": arm.id, "toolkit": spec["toolkit"], "ok": False}
    try:
        arm.arm_guard()
        arm.launch()
        arm.wait_first_frame(30)
        system.sleep(3.0)
        pid_text = system.run(["systemctl", "show", "-p", "MainPID", "--value", arm.unit])[1].strip()
        pid = int(pid_text) if pid_text.isdigit() and int(pid_text) > 0 else None
        maps = system.read(f"/proc/{pid}/maps", "") if pid else ""
        libs = sorted({Path(m.group(1)).name for m in re.finditer(r"(/nix/store/\S+\.so[\w.]*)", maps)})
        ident["mapped_graphics_libs"] = [l for l in libs if re.match(r"lib(EGL|GL|GLES|vulkan|gbm|drm|wayland-egl)", l)]
        ident["mapped_qt_libs"] = [l for l in libs if l.startswith("libQt6")]
        environ = (system.read(f"/proc/{pid}/environ", "") or "") if pid else ""
        wanted = ("QT_QPA_PLATFORM", "QT_QUICK_BACKEND", "QSG_INFO", "QSG_RHI_BACKEND", "QT_WAYLAND_DISABLE_WINDOWDECORATION")
        ident["effective_env"] = {k: v for k, v in (e.split("=", 1) for e in environ.split("\0") if "=" in e) if k in wanted}
        ident["qsg_rhi_backend_inherited"] = "QSG_RHI_BACKEND" in ident["effective_env"]
        ident["start_line"] = next((l for l in arm.events_text().splitlines() if '"start"' in l), None)
        err = system.read(arm.dir / "client.err", "") or ""
        ident["bound_protocols"] = sorted(set(re.findall(r'-> wl_registry#\d+\.bind\(\d+, "(\w+)"', err)))
        fmt_names = {"0": "ARGB8888", "1": "XRGB8888"}
        ident["create_buffer_formats"] = sorted({fmt_names.get(f, f) for f in re.findall(
            r"wl_shm_pool#\d+\.create_buffer\(new id wl_buffer#\d+, \d+, \d+, \d+, \d+, (\d+)\)", err)})
        ident["attach_count"] = len(re.findall(r"wl_surface#\d+\.attach\(wl_buffer#", err))
        ident["linux_dmabuf_requests"] = len(re.findall(r"-> zwp_linux_\w+#\d+\.", err)) + \
            len([p for p in ident["bound_protocols"] if "dmabuf" in p])
        ident["wl_drm_requests"] = len(re.findall(r"-> wl_drm#\d+\.", err)) + \
            len([p for p in ident["bound_protocols"] if p == "wl_drm"])
        qsg = [l.strip()[:160] for l in (system.run(["journalctl", "-u", arm.unit, "--no-pager", "-o", "cat"])[1]).splitlines()
               if re.search(r"QSG|scene graph|software|backend|RHI", l, re.I)][:12]
        ident["qsg_info_lines"] = qsg
        ident["qsg_info_in_stderr"] = [l.strip()[:160] for l in err.splitlines() if re.search(r"QSG|software|backend|RHI", l, re.I) and "wl_" not in l][:12]
        ident["ok"] = True
    finally:
        res = arm.restore("identity-finally")
        ident["restoration"] = res
        system.write(arm.dir / "identity.json", json.dumps(ident, indent=1))
    print(json.dumps({"ok": ident["ok"] and res["ok"]}))
    return 0 if ident["ok"] and res["ok"] else 1


def cmd_verify(args, system=None):
    """Read-only: the current compositor state, for the controller to compare with pre.json."""
    system = system or System()
    spec = json.loads(system.read(STATE_DIR / args.id / "spec.json", "null") or "null")
    if not spec:
        print(json.dumps({"ok": False, "reason": "no spec for run"}))
        return 1
    snap = Arm(system, spec).snapshot()
    pre = json.loads(system.read(STATE_DIR / args.id / "pre.json", "null") or "null")
    ok = bool(pre) and snap["shell_active"] and not snap["qtq_units"] and \
        snap["sway_pid"] == pre["sway_pid"] and snap["focused_app_id"] == pre["focused_app_id"] and \
        spec["app_id"] not in snap["windows"]
    print(json.dumps({"ok": ok, "snapshot": snap, "pre": pre}))
    return 0 if ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("arm", "identity"):
        p = sub.add_parser(name)
        p.add_argument("--spec", required=True)
    r = sub.add_parser("restore")
    r.add_argument("--id", required=True)
    r.add_argument("--reason", default="manual")
    v = sub.add_parser("verify")
    v.add_argument("--id", required=True)
    args = parser.parse_args(argv)
    return {"arm": cmd_arm, "identity": cmd_identity, "restore": cmd_restore, "verify": cmd_verify}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
