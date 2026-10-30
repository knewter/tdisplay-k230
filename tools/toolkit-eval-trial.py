#!/usr/bin/env python3
"""Matched-pair board trial of a candidate toolkit client (egui, later Sidestep)
against the shared wl_shm baseline, built on the Qt trial's harness:

  tools/qtquick_board.py         host controller helpers (board lock per arm, closure copy, gates)
  tools/qtquick_board_runner.py  on-board deadline-controlled runner (systemd-run unit, guard timer,
                                 uinput touch, grim captures, restoration)
  tools/qtquick_analysis.py      per-run metrics and comparison

This file only adds a candidate slot, the WAYLAND_DEBUG identity check for clients
that do not link libwayland, and the summary tables.

  toolkit-eval-trial.py --self-test
  toolkit-eval-trial.py board --name egui --candidate STORE_OUT --baseline STORE_OUT --out DIR
  toolkit-eval-trial.py analyse --out DIR

Evidence class: board run with injected uinput touch, native grim captures and
client commit timestamps. Never glass, never optical. The board stage needs the
host board lock (taken per arm by the controller) and changes nothing persistent.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qtquick_analysis as qa  # noqa: E402
import qtquick_board as qb  # noqa: E402

APP_IDS = {"egui": "egui-software-probe", "baseline": "qtquick-shm-baseline"}
BINARIES = {"egui": "bin/egui-software-probe", "baseline": "bin/qtquick-shm-baseline"}
qb.APP_IDS.update(APP_IDS)


def manifest_for(name, candidate, baseline, system, created):
    """A trial manifest in the shape qtquick_board.make_spec reads (candidate in the `name` slot)."""
    art = {name: {"store_path": candidate, "binary": BINARIES[name]},
           "baseline": {"store_path": baseline, "binary": BINARIES["baseline"]}}
    manifest = {"schema": "toolkit-eval-manifest/1", "created_utc": created, "workload": dict(qa.WORKLOAD),
                "ceilings": dict(qa.CEILINGS), "artifacts": art, "system": {"toplevel": system}}
    manifest["hash"] = qa.digest(manifest)
    return manifest


def identity_from_stderr(err_text, ident):
    """Software/wl_shm route from a WAYLAND_DEBUG=client log in either libwayland ('#') or
    wayland-rs ('@') format, plus the libraries mapped into the process."""
    binds = sorted(set(re.findall(r'wl_registry[#@]\d+\.bind\(\d+, "(\w+)"', err_text)))
    attaches = len(re.findall(r"wl_surface[#@]\d+\.attach\(wl_buffer", err_text))
    pools = len(re.findall(r"wl_shm_pool[#@]\d+\.create_buffer", err_text))
    gpu = [b for b in binds if "dmabuf" in b or b in ("wl_drm", "wp_drm_lease_device_v1")]
    gpu_libs = ident.get("mapped_graphics_libs", [])
    ident.update({"bound_protocols": binds, "attach_count": attaches, "shm_create_buffer_count": pools,
                  "gpu_protocols_bound": gpu})
    ok = attaches > 0 and pools > 0 and not gpu and not gpu_libs
    ident["software_route"] = bool(ok)
    return ok


POINTER_REMOTE = "/var/tmp/toolkit-eval/board-pointer.py"
_orig_locked = qb.locked


def locked_with_stat(command, timeout):
    """qtquick_board.locked, with whole-system CPU counters read on the board before and after the arm
    (the CPU is shared with other agents' work; this shows whether anything else ran)."""
    if command and command[-1].startswith(("/nix/store/", "'/nix/store/")):
        inner = command[-1]
        py = inner.split()[0]
        # The panel blanks when idle and grim then waits forever for a frame; a pointer move is the
        # same wake-up any input gives (swayidle's resume), and the idle dimmer undoes its own dimming.
        wake = (f"{py} {POINTER_REMOTE} 1232x568 'move 600 300; wait 300; move 610 300' >/dev/null 2>&1; sleep 2; ")
        command = command[:-1] + [wake + "S1=$(head -1 /proc/stat); " + inner +
                                  "; rc=$?; S2=$(head -1 /proc/stat); echo STAT1 $S1; echo STAT2 $S2; exit $rc"]
    return _orig_locked(command, timeout)


qb.locked = locked_with_stat


# Observed on the board 2026-10-30: the runner's uinput touchscreen does not reach the client at a stable
# place. The panel is the transform-270 output DSI-1; the first arm of one run saw taps rotated a quarter turn
# (client log: injected (300,400) arrived as (363,138)), a pre-rotated retry landed correctly in the next arm,
# and a later arm was rotated again. Sway's touch mapping for this device is not something the runner fixes
# (type:touch calibration is the identity, and a follow-output service rewrites it). An absolute *pointer* is
# placed by the compositor in layout coordinates, so it lands where aimed; this tool therefore replaces the
# runner's Touch class with a uinput absolute pointer pinned to DSI-1. The clients get wl_pointer events, not
# wl_touch; that is recorded as the evidence class ("injected uinput absolute pointer").
_POINTER_CLASS = """class Pointer:
    NAME = b"toolkit_eval_pointer"
    IDENT = "1:1:toolkit_eval_pointer"

    def __init__(self, system):
        import fcntl
        import struct
        self.system, self.fcntl, self.struct = system, fcntl, struct
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        for bit in (0, 1, 3):
            fcntl.ioctl(self.fd, 0x40045564, bit)
        fcntl.ioctl(self.fd, 0x40045565, 0x110)
        for axis in (0, 1):
            fcntl.ioctl(self.fd, 0x40045567, axis)
        mx = [0] * 64
        mx[0] = mx[1] = 65535
        dev = struct.pack("80sHHHHi", self.NAME, 3, 1, 1, 1, 0)
        dev += struct.pack("64i", *mx) + struct.pack("64i", *[0] * 64) * 3
        os.write(self.fd, dev)
        fcntl.ioctl(self.fd, 0x5501)
        system.sleep(1.0)  # the compositor adds the device
        system.run(system.shell_env(["swaymsg", "input", self.IDENT, "map_to_output", "DSI-1"]), timeout=15)
        system.sleep(0.3)

    def _emit(self, t, c, v):
        now = time.time()
        sec = int(now)
        os.write(self.fd, self.struct.pack("llHHi", sec, int((now - sec) * 1e6), t, c, v))

    def _pos(self, x, y):
        self._emit(3, 0, min(65535, max(0, round(x * 65535 / (OUTPUT_W - 1)))))
        self._emit(3, 1, min(65535, max(0, round(y * 65535 / (OUTPUT_H - 1)))))
        self._emit(0, 0, 0)

    def down(self, x, y):
        self._pos(x, y)
        self._emit(1, 0x110, 1)
        self._emit(0, 0, 0)

    def move(self, x, y):
        self._pos(x, y)

    def up(self):
        self._emit(1, 0x110, 0)
        self._emit(0, 0, 0)

    def tap(self, x, y, hold_s=0.06):
        self.down(x, y)
        self.system.sleep(hold_s)
        self.up()

    def drag(self, x0, y0, x1, y1, ms):
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


Touch = Pointer


class Arm:
"""

# The runner's functional checks assume the scene as launched (list at the top, mover at the left, row 0
# unselected) but run them after the 30 s of scripted interaction, which leaves it anywhere. Put the scene
# back first, using only injected touch and a 1x1 grim read of row 0's colour.
_OLD_FUNC = """        t = self.touch
        self.capture("f0-initial")
"""
_NEW_FUNC = """        t = self.touch
        for _ in range(8):
            t.drag(ox + 300, oy + 130, ox + 300, oy + 520, 160)   # content toward the top
            self.s.sleep(0.45)
        t.tap(ox + 1100, oy + 250)                                # mover back left if it ended on the right
        self.s.sleep(0.9)
        if self.row0_selected(ox, oy):
            t.tap(ox + 300, oy + 130)                             # any row toggles the shared flag
            self.s.sleep(0.6)
        self.record["functional_reset"] = {"row0_selected_after_reset": self.row0_selected(ox, oy)}
        self.capture("f0-initial")
"""
_ROW0_HELPER = """    def row0_selected(self, ox, oy):
        import struct
        import zlib
        path = self.dir / "px.png"
        rc, _ = self.s.run(self.s.shell_env(["grim", "-g", f"{ox + 40},{oy + 105} 1x1", str(path)]),
                           timeout=40)
        if rc:
            return False
        data = open(path, "rb").read()
        pos, idat = 8, b""
        while pos < len(data):
            n = struct.unpack(">I", data[pos:pos + 4])[0]
            if data[pos + 4:pos + 8] == b"IDAT":
                idat += data[pos + 8:pos + 8 + n]
            pos += 12 + n
        r, g, b = zlib.decompress(idat)[1:4]
        return abs(r - 0x4b) < 20 and abs(g - 0x6e) < 20 and abs(b - 0xa8) < 20

    def functional(self, win):
"""


def patched_runner_source(source):
    if "\nclass Arm:\n" not in source or _OLD_FUNC not in source:
        raise RuntimeError("tools/qtquick_board_runner.py no longer has the Arm class and functional "
                           "preamble this tool patches; check whether the runner handles them itself")
    source = source.replace("\nclass Arm:\n", "\n" + _POINTER_CLASS, 1).replace(_OLD_FUNC, _NEW_FUNC)
    return source.replace("    def functional(self, win):\n", _ROW0_HELPER, 1)


def upload_runner_patched():
    qb.ssh(f"install -d -m 0755 {qb.REMOTE}")
    src = patched_runner_source((qb.ROOT / "tools/qtquick_board_runner.py").read_text())
    res = qb.ssh(f"cat > {qb.REMOTE}/runner.py && chmod 0755 {qb.REMOTE}/runner.py", stdin=src)
    if res.returncode:
        raise RuntimeError("runner upload failed")


qb.upload_runner = upload_runner_patched


def system_busy_from_stdout(text):
    """(busy_fraction, busy_jiffies, total_jiffies) from the STAT1/STAT2 lines, or None."""
    rows = {}
    for line in text.splitlines():
        m = re.match(r"STAT([12]) cpu\s+(.*)", line)
        if m:
            rows[m.group(1)] = [int(x) for x in m.group(2).split()]
    if len(rows) != 2:
        return None
    d = [b - a for a, b in zip(rows["1"], rows["2"])]
    idle = d[3] + d[4]
    total = sum(d[:8])
    return ((total - idle) / total if total else None), total - idle, total


QUIET_PROBE = (r"a=$(awk '/^cpu /{print $2+$3+$4+$7+$8+$9, $5+$6}' /proc/stat); sleep 4; "
               r"b=$(awk '/^cpu /{print $2+$3+$4+$7+$8+$9, $5+$6}' /proc/stat); "
               r"echo $a $b; cat /proc/loadavg; ps -eo pcpu,comm --sort=-pcpu | sed -n 2,4p")


def board_busy_fraction():
    """Busy fraction of the single CPU over 4 s, and the top processes, read over ssh. (None, text) if unreadable."""
    out = qb.ssh(QUIET_PROBE, timeout=60).stdout.splitlines()
    try:
        b0, i0, b1, i1 = (int(x) for x in out[0].split())
        busy, idle = b1 - b0, i1 - i0
        return busy / max(busy + idle, 1), " | ".join(out[1:])
    except (ValueError, IndexError):
        return None, " | ".join(out)


def wait_for_quiet(label, log, limit_s=900, threshold=0.2):
    """Other agents share the board; start an arm only when it is quiet, and record what we saw."""
    start = time.time()
    while True:
        frac, detail = board_busy_fraction()
        log.append({"label": label, "busy_fraction": frac, "detail": detail[:200], "waited_s": round(time.time() - start)})
        if frac is not None and frac < threshold:
            return True
        if time.time() - start > limit_s:
            return False
        time.sleep(20)


def board(args):
    out = Path(args.out)
    name = args.name
    out.mkdir(parents=True, exist_ok=True)
    (out / "runs").mkdir(exist_ok=True)
    (out / "restoration").mkdir(exist_ok=True)
    py = qb.python_path()
    system = qb.ssh("readlink /run/current-system").stdout.strip()
    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest = manifest_for(name, args.candidate, args.baseline, system, created)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    arms = [t for t in (name, "baseline") if not args.only or t in args.only]
    for toolkit in arms:
        qb.copy_closure(manifest["artifacts"][toolkit]["store_path"])
    qb.upload_runner()
    qb.ssh("install -d -m 0755 /var/tmp/toolkit-eval")
    qb.ssh(f"cat > {POINTER_REMOTE} && chmod 0755 {POINTER_REMOTE}", stdin=(qb.ROOT / "tools/board-pointer.py").read_text())
    log, identities = [], {}
    for toolkit in arms:
        spec = qb.make_spec(manifest, toolkit, 0, 0, deadline_s=60, exit_after_s=20)
        spec["id"] = spec["id"].replace("p00", "ident")
        outcome = qb.run_remote(py, "identity", spec, out, f"identity-{toolkit}")
        log.append(outcome)
        raw = out / "raw" / spec["id"]
        path = raw / "identity.json"
        ident = json.loads(path.read_text()) if path.is_file() else {"ok": False}
        err = (raw / "client.err").read_text() if (raw / "client.err").is_file() else ""
        identity_from_stderr(err, ident)
        identities[toolkit] = ident
        (out / f"identity-{toolkit}.json").write_text(json.dumps(ident, indent=2) + "\n")
        (out / "restoration" / f"identity-{toolkit}.json").write_text(
            json.dumps(ident.get("restoration", {"ok": False}), indent=2) + "\n")
    for pair in range(1, args.pairs + 1):
        order = (name, "baseline") if pair != 2 else ("baseline", name)
        for position, toolkit in enumerate(order, 1):
            if args.only and toolkit not in args.only:
                continue
            spec = qb.make_spec(manifest, toolkit, pair, position, idle_s=args.idle, active_s=args.active,
                                exit_after_s=args.idle + args.active + 70, deadline_s=args.idle + args.active + 150)
            quiet = wait_for_quiet(f"pair{pair}-{toolkit}", log)
            outcome = qb.run_remote(py, "arm", spec, out, f"pair{pair}-{toolkit}")
            outcome["quiet_before"] = quiet
            log.append(outcome)
            raw = out / "raw" / spec["id"]
            run_file = raw / "run.json"
            if run_file.is_file():
                run = json.loads(run_file.read_text())
                run["gates"] = qb.gates_from_captures(run, raw, {"software_route": identities[toolkit].get("software_route")})
                for gate in qa.FUNCTIONAL_GATES:
                    if gate in run["gates"] and gate not in ("bounded_lifetime", "restored"):
                        run["functional"][gate] = run["gates"][gate]
                run["functional"]["software_route"] = run["gates"].get("software_route")
                events = raw / "client.jsonl"
                run["events_file"] = f"pair{pair}-{toolkit}.jsonl"
                (out / "runs" / f"pair{pair}-{toolkit}.json").write_text(json.dumps(run, indent=1) + "\n")
                (out / "runs" / run["events_file"]).write_text(events.read_text() if events.is_file() else "")
                (out / "restoration" / f"pair{pair}-{toolkit}.json").write_text(
                    json.dumps(run.get("restoration", {"ok": False}), indent=2) + "\n")
            else:
                (out / "restoration" / f"pair{pair}-{toolkit}.json").write_text(
                    json.dumps({"ok": False, "reason": "no run record"}) + "\n")
            print(f"pair{pair} {toolkit}: rc={outcome['returncode']} {outcome['stdout'][-120:]}", flush=True)
            time.sleep(8)  # settle between arms, board lock released
    (out / "trial-log.json").write_text(json.dumps(log, indent=2) + "\n")
    return 0


def extra_metrics(events, window, metrics):
    gaps = qa.commit_gaps(events, window) if window[1] else []
    lat = qa.input_to_commit(events, window) if window[1] else []
    renders = [e["r"] / 1000.0 for e in events if e["e"] == "commit" and "r" in e and window[0] <= e["t"] < window[1]]
    metrics["commit_gap_p50_ms"] = qa.percentile(gaps, 0.5)
    metrics["commit_gap_p99_ms"] = qa.percentile(gaps, 0.99)
    metrics["input_to_commit_p99_ms"] = qa.percentile(lat, 0.99)
    metrics["commits_in_active"] = len(gaps) + 1 if gaps else 0
    metrics["render_p50_ms"] = qa.percentile(renders, 0.5)
    metrics["render_p95_ms"] = qa.percentile(renders, 0.95)
    metrics["render_max_ms"] = max(renders) if renders else None
    return metrics


def load_arms(out):
    arms = []
    busy = {}
    log_file = Path(out) / "trial-log.json"
    if log_file.is_file():
        for row in json.loads(log_file.read_text()):
            stat = system_busy_from_stdout(row.get("stdout", "")) if row.get("label") else None
            if stat:
                busy[row["label"]] = stat
    for run_file in sorted((Path(out) / "runs").glob("pair*-*.json")):
        run = json.loads(run_file.read_text())
        events_file = run_file.with_name(run.get("events_file", ""))
        events = qa.parse_events(events_file.read_text()) if events_file.is_file() else []
        res = qa.analyse_run(run, events)
        active = run.get("phases", {}).get("active", {})
        window = (active.get("start_mono_ms", 0), active.get("end_mono_ms", 0))
        extra_metrics(events, window, res["metrics"])
        samples = run.get("phases", {}).get("active", {}).get("mem_used_kib_samples") or []
        res.update({"name": run["toolkit"], "pair": run["pair"], "functional": qa.functional_results(run),
                    "gates": {k: v for k, v in run.get("gates", {}).items() if not k.startswith("_")},
                    "restored": bool(run.get("functional", {}).get("restored")), "status": run.get("status"),
                    "arm_system_busy_pct": (100 * busy[f"pair{run['pair']}-{run['toolkit']}"][0]
                                            if f"pair{run['pair']}-{run['toolkit']}" in busy else None),
                    "mem_samples": samples})
        arms.append(res)
    return arms


KEYS = ["arm_system_busy_pct", "startup_ms", "incremental_memory_mib", "idle_client_cpu_pct", "idle_sway_cpu_pct", "active_client_cpu_pct",
        "active_sway_cpu_pct", "active_combined_cpu_pct", "commit_gap_p50_ms", "commit_gap_p95_ms", "commit_gap_max_ms",
        "commits_in_active", "render_p50_ms", "render_p95_ms", "render_max_ms", "input_to_commit_p50_ms",
        "input_to_commit_p95_ms", "input_to_commit_p99_ms", "input_samples", "interactions"]


def summarise(arms, name):
    lines = ["| metric | " + " | ".join(f"{a['name']} #{a['pair']}" for a in arms) + " |",
             "| --- | " + " | ".join("---:" for _ in arms) + " |"]
    for k in KEYS:
        vals = [a["metrics"].get(k, a.get(k)) for a in arms]
        lines.append(f"| {k} | " + " | ".join("-" if v is None else f"{v:.2f}" for v in vals) + " |")
    lines.append("| restored | " + " | ".join("yes" if a["restored"] else "NO" for a in arms) + " |")
    gates = sorted({g for a in arms for g in a["functional"]})
    for g in gates:
        lines.append(f"| gate {g} | " + " | ".join(a["functional"].get(g, "-") for a in arms) + " |")
    cand = sorted((a for a in arms if a["name"] == name), key=lambda a: a["pair"])
    base = sorted((a for a in arms if a["name"] == "baseline"), key=lambda a: a["pair"])
    comparison = qa.compare(cand, base, baseline_ok=True) if cand and base and len(cand) == len(base) else {}
    return "\n".join(lines) + "\n", comparison


def analyse(args):
    out = Path(args.out)
    arms = load_arms(out)
    table, comparison = summarise(arms, args.name)
    (out / "summary.md").write_text(table)
    (out / "summary.json").write_text(json.dumps({"arms": arms, "comparison": comparison}, indent=1) + "\n")
    print(table)
    for key, row in comparison.items():
        print(key, row.get("status"), {k: (round(v, 2) if isinstance(v, float) else v) for k, v in row.items()
                                       if k in ("qt_mean", "baseline_mean", "regression_pct")})
    return 0 if arms and all(a["restored"] for a in arms) else 1


class SelfTest(unittest.TestCase):
    def test_identity_accepts_wayland_rs_log_without_gpu(self):
        err = ('[1.0]  -> wl_registry@2.bind(1, "wl_compositor", 6, new id [unknown]@3)\n'
               '[1.1]  -> wl_shm_pool@8.create_buffer(new id wl_buffer@9, 0, 1232, 568, 4928, 1)\n'
               '[1.2]  -> wl_surface@5.attach(wl_buffer@9, 0, 0)\n')
        ident = {"mapped_graphics_libs": []}
        self.assertTrue(identity_from_stderr(err, ident))
        self.assertEqual(ident["attach_count"], 1)

    def test_identity_rejects_dmabuf_or_gl_libs(self):
        err = ('-> wl_registry#2.bind(5, "zwp_linux_dmabuf_v1", 4, new id)\n'
               'wl_shm_pool#8.create_buffer(x)\nwl_surface#5.attach(wl_buffer#9)\n')
        self.assertFalse(identity_from_stderr(err, {"mapped_graphics_libs": []}))
        self.assertFalse(identity_from_stderr(err.replace("zwp_linux_dmabuf_v1", "wl_shm"), {"mapped_graphics_libs": ["libEGL.so.1"]}))
        self.assertFalse(identity_from_stderr("", {"mapped_graphics_libs": []}))

    def test_runner_patch_applies_and_compiles(self):
        src = patched_runner_source((qb.ROOT / "tools/qtquick_board_runner.py").read_text())
        compile(src, "runner.py", "exec")
        self.assertIn("row0_selected", src)
        self.assertIn("Touch = Pointer", src)
        with self.assertRaises(RuntimeError):
            patched_runner_source("def other(): pass")

    def test_manifest_hash_changes_with_artifact(self):
        a = manifest_for("egui", "/nix/store/" + "a" * 32 + "-x", "/nix/store/" + "b" * 32 + "-y", "/nix/store/" + "c" * 32 + "-s", "t")
        b = manifest_for("egui", "/nix/store/" + "d" * 32 + "-x", "/nix/store/" + "b" * 32 + "-y", "/nix/store/" + "c" * 32 + "-s", "t")
        self.assertNotEqual(a["hash"], b["hash"])
        spec = qb.make_spec(a, "egui", 1, 1)
        self.assertEqual(spec["app_id"], "egui-software-probe")
        self.assertTrue(spec["binary"].endswith("/bin/egui-software-probe"))

    def test_load_and_summarise_a_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            runs.mkdir()
            for pair in (1, 2, 3):
                for name in ("egui", "baseline"):
                    ev = [{"e": "first_frame", "t": 400}]
                    for i in range(30):
                        ev += [{"e": "input", "t": 10_000 + i * 900, "k": "press"},
                               {"e": "commit", "t": 10_000 + i * 900 + 20, "r": 12000}]
                    (runs / f"pair{pair}-{name}.jsonl").write_text("\n".join(json.dumps(e) for e in ev))
                    (runs / f"pair{pair}-{name}.json").write_text(json.dumps({
                        "schema": qa.RUN_SCHEMA, "toolkit": name, "pair": pair, "launch_mono_ms": 100,
                        "events_file": f"pair{pair}-{name}.jsonl", "status": "ok",
                        "phases": {"idle": {"elapsed_s": 30, "client_cpu_us": 1, "sway_cpu_us": 1},
                                   "active": {"elapsed_s": 30, "client_cpu_us": 3_000_000, "sway_cpu_us": 3_000_000,
                                              "start_mono_ms": 9_000, "end_mono_ms": 40_000}},
                        "memory": {"before_kib": 0, "active_used_kib": 10 * 1024},
                        "interactions": [{"kind": "tap"}] * 30, "functional": {"restored": True}}))
            arms = load_arms(tmp)
            self.assertEqual(len(arms), 6)
            self.assertEqual(arms[0]["metrics"]["render_p95_ms"], 12.0)
            table, comparison = summarise(arms, "egui")
            self.assertIn("render_p95_ms", table)
            self.assertEqual(comparison["active_combined_cpu_pct"]["status"], "WITHIN_10_PCT")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("board")
    b.add_argument("--name", required=True, choices=("egui",))
    b.add_argument("--candidate", required=True)
    b.add_argument("--baseline", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--pairs", type=int, default=3)
    b.add_argument("--only", nargs="*", help="run only these arms (debugging; a trial needs both)")
    b.add_argument("--idle", type=int, default=30)
    b.add_argument("--active", type=int, default=30)
    a = sub.add_parser("analyse")
    a.add_argument("--out", required=True)
    a.add_argument("--name", default="egui")
    args = ap.parse_args(argv)
    if args.self_test:
        return 0 if unittest.TextTestRunner(verbosity=1).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(SelfTest)).wasSuccessful() else 1
    if args.cmd == "board":
        return board(args)
    if args.cmd == "analyse":
        return analyse(args)
    ap.print_help()
    return 64


if __name__ == "__main__":
    sys.exit(main())
