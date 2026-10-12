#!/usr/bin/env python3
"""One bounded board run: swap the Rust ELF through a runtime drop-in, run the
13.1 workload through tools/theme-picker-profile.py `capture`, then restore.

Board, root, board python. Software input only (the virtual touchscreen named
'K230 injected touchscreen'). An independent systemd timer restores the normal
service even if this process dies.

  run.py input-up
  run.py run --label LABEL --kind baseline|candidate --exe ELF --mode off|counters|trace
             --out DIR [--trace-seconds N]
"""
import argparse, hashlib, json, os, pwd, re, subprocess, sys, time, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT_UNIT = "k230-theme-session-input"
DROPIN = "92-theme-session.conf"
TIMER = "k230-theme-session-restore"
SH = ["runuser", "-u", "shell", "--", "env", "XDG_RUNTIME_DIR=/run/shell", "WAYLAND_DISPLAY=wayland-1"]
NAME = "K230 injected touchscreen"


def call(argv, check=True, timeout=60):
    return subprocess.run(argv, check=check, capture_output=True, text=True, timeout=timeout).stdout


def virtual_devices():
    return [p.parent.parent.name for p in Path("/sys/class/input").glob("event*/device/name")
            if p.read_text().strip() == NAME and str(p.resolve()).startswith("/sys/devices/virtual/input/")]


def input_up():
    subprocess.run(["systemctl", "stop", INPUT_UNIT], check=False, capture_output=True)
    time.sleep(0.5)
    desc = call(["evemu-describe", "/dev/input/event1"])
    desc, n = re.subn(r"^N:.*$", "N: " + NAME, desc, flags=re.M)
    assert n == 1
    path = HERE / "touch.desc"
    path.write_text(desc)
    call(["systemd-run", "--unit=" + INPUT_UNIT, "--collect", "--property=Type=exec", "--property=RuntimeMaxSec=14400s",
          "evemu-device", str(path)])
    for _ in range(100):
        found = virtual_devices()
        if len(found) == 1:
            print("DEVICE", "/dev/input/" + found[0], flush=True)
            return
        time.sleep(0.1)
    raise RuntimeError("virtual touch unavailable")


def restore():
    for unit in ("shell-ui", "theme-helper"):
        Path(f"/run/systemd/system/{unit}.service.d/{DROPIN}").unlink(missing_ok=True)
    call(["systemctl", "daemon-reload"], check=False)
    call(["systemctl", "restart", "theme-helper", "shell-ui"], check=False, timeout=90)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def gesture_session(a, out, device, state_root, troot):
    """Injected gesture programs, one fresh picker opening per gesture, native capture after each settle."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("gestures", HERE / "gestures.py")
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    active = Path(state_root) / "active"
    before = str(active.resolve(strict=True))
    ident = {u: call(["systemctl", "show", u, "-p", "MainPID", "--value"]).strip() for u in ("shell-ui", "theme-helper", "shell")}
    ticks = {u: Path("/proc/%s/stat" % p).read_text().rsplit(")", 1)[1].split()[19] for u, p in ident.items()}
    records, shots = [], out / "shots"
    shots.mkdir(exist_ok=True)

    def tap(xy, wait):
        g.inject(device, [(0, "down", *xy), (80, "up", *xy)])
        time.sleep(wait)

    tap(g.THEMES_TAP, 9)
    n = 0
    for rep in range(a.reps):
        for name in g.GESTURES:
            rec = {"row": a.row, "gesture": name, "rep": rep, "program": g.program(name, a.row)}
            rec["start_s"] = time.monotonic()
            log = g.inject(device, rec["program"])
            rec.update(down_s=log["down_s"], up_s=log["up_s"], moves=log["moves"])
            time.sleep(a.settle)
            rec["end_s"] = time.monotonic()
            png = troot / ("g%02d.png" % n)  # native capture, outside the gesture window
            call(SH + ["grim", "-s", "0.4", str(png)])
            (shots / ("g%02d-%s-%s-r%d.png" % (n, a.row, name, rep))).write_bytes(png.read_bytes())
            rec["generation_unchanged"] = str(active.resolve(strict=True)) == before
            rec["identities_unchanged"] = all(
                call(["systemctl", "show", u, "-p", "MainPID", "--value"]).strip() == p
                and Path("/proc/%s/stat" % p).read_text().rsplit(")", 1)[1].split()[19] == ticks[u] for u, p in ident.items())
            records.append(rec)
            n += 1
            if not (rec["generation_unchanged"] and rec["identities_unchanged"]):
                raise RuntimeError("generation or process identity changed during %s" % name)
            tap(g.BACK_TAP, 1.5)
            tap(g.THEMES_TAP, 5)
    (out / "gestures.private.json").write_text(json.dumps({"records": records, "monotonic_end_s": time.monotonic()}))


def visible_session(a, out, device, state_root, troot):
    """Native stills (outside any timing pass) showing both rows respond to an injected swipe."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("gestures", HERE / "gestures.py")
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    active = Path(state_root) / "active"
    before = str(active.resolve(strict=True))
    shots = out / "shots"
    shots.mkdir(exist_ok=True)

    def shot(name):
        png = troot / (name + ".png")
        call(SH + ["grim", "-s", "0.5", str(png)])
        (shots / (name + ".png")).write_bytes(png.read_bytes())

    g.inject(device, [(0, "down", *g.THEMES_TAP), (80, "up", *g.THEMES_TAP)])
    time.sleep(12)
    shot("0-open")
    for row in ("theme", "background"):
        g.inject(device, [(0, "down", 430, g.ROW_Y[row]), *g.line(0, 430, 190, g.ROW_Y[row], 200, 10), (210, "up", 190, g.ROW_Y[row])])
        time.sleep(3)
        shot("1-after-" + row + "-swipe")
    assert str(active.resolve(strict=True)) == before, "generation changed"
    (out / "visible.json").write_text(json.dumps({"generation_unchanged": True}))


def video_session(a, out, device, state_root, troot):
    """Sampled native Wayland screencopy (tools/sample-grim-frames.sh) of an injected browsing sequence. Not a timing pass."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("gestures", HERE / "gestures.py")
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    active = Path(state_root) / "active"
    before = str(active.resolve(strict=True))
    g.inject(device, [(0, "down", *g.THEMES_TAP), (80, "up", *g.THEMES_TAP)])
    time.sleep(10)
    half = troot / "grim-half"
    half.write_text("#!/bin/sh\nexec grim -s 0.5 \"$@\"\n")
    half.chmod(0o555)
    os.chown(half, pwd.getpwnam("shell").pw_uid, pwd.getpwnam("shell").pw_gid)
    sdir = troot / "samples"
    sdir.mkdir()
    os.chown(sdir, pwd.getpwnam("shell").pw_uid, pwd.getpwnam("shell").pw_gid)
    env = os.environ.copy()
    script = troot / "sample-grim-frames.sh"  # /root is not readable by the shell user
    script.write_bytes((HERE / "sample-grim-frames.sh").read_bytes())
    script.chmod(0o555)
    os.chown(script, pwd.getpwnam("shell").pw_uid, pwd.getpwnam("shell").pw_gid)
    sampler = subprocess.Popen(SH + ["/run/current-system/sw/bin/bash", str(script), "browse", "--description",
                                     "injected theme and background swipes", "--provenance", "injected", "--duration", "16", "--interval", "0.5",
                                     "--grim", str(half), "--output-dir", str(sdir)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    time.sleep(1.0)
    for i, (x, x2) in enumerate([(430, 190)] * 2 + [(190, 430)]):
        g.inject(device, [(0, "down", x, 430), *g.line(0, x, x2, 430, 200, 10), (210, "up", x2, 430)])
        time.sleep(1.2)
    for i, (x, x2) in enumerate([(430, 190), (190, 430)]):
        g.inject(device, [(0, "down", x, 990), *g.line(0, x, x2, 990, 200, 10), (210, "up", x2, 990)])
        time.sleep(1.2)
    outp = sampler.communicate(timeout=60)[0]
    print("SAMPLER", outp.strip()[-200:], flush=True)
    assert str(active.resolve(strict=True)) == before, "generation changed"
    call(["tar", "-C", str(sdir), "-czf", str(out / "samples.tar.gz"), "."])


def run(a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    assert re.fullmatch(r"/nix/store/[a-z0-9]{32}-[^/ \n]+/bin/k230-shell-rust", a.exe)
    os.umask(0o077)
    shell = pwd.getpwnam("shell")
    troot = Path("/run/shell/theme-session") / (a.label + "-" + uuid.uuid4().hex[:8])
    troot.parent.mkdir(mode=0o700, exist_ok=True)
    os.chown(troot.parent, shell.pw_uid, shell.pw_gid)
    troot.mkdir(mode=0o700)
    os.chown(troot, shell.pw_uid, shell.pw_gid)
    found = virtual_devices()
    assert len(found) == 1
    device = "/dev/input/" + found[0]
    state_root = "/home/shell/.local/state/omarchy/current"
    # the installed wrapper, with only its final ELF replaced
    normal = call(["systemctl", "show", "shell-ui", "-p", "ExecStart", "--value"])
    wrapper_path = re.search(r"path=(/nix/store/[^ ;]+/bin/k230-shell-rust)", normal)[1]
    original = Path(wrapper_path).read_text()
    text, n = re.subn(r"(?m)^exec /nix/store/[^ ]+/bin/k230-shell-rust", "exec " + a.exe, original)
    assert n == 1
    wrapper = troot / "shell-wrapper"
    wrapper.write_text(text)
    wrapper.chmod(0o555)
    os.chown(wrapper, shell.pw_uid, shell.pw_gid)
    cleanup = HERE / "restore.sh"
    cleanup.write_text("#!/bin/sh\nrm -f /run/systemd/system/shell-ui.service.d/%s /run/systemd/system/theme-helper.service.d/%s\n"
                       "systemctl daemon-reload\nsystemctl restart theme-helper shell-ui\n" % (DROPIN, DROPIN))
    cleanup.chmod(0o700)
    trace = troot / "rust.json"
    trace_id = uuid.uuid4().hex
    meta = {"label": a.label, "kind": a.kind, "exe": a.exe, "mode": a.mode, "started_utc": now(),
            "normal_wrapper_sha256": hashlib.sha256(original.encode()).hexdigest(),
            "trial_wrapper_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "current_system": str(Path("/run/current-system").resolve())}
    dropin = Path("/run/systemd/system/shell-ui.service.d") / DROPIN
    try:
        dropin.parent.mkdir(exist_ok=True)
        assert not dropin.exists()
        env = ""
        if a.mode != "off":
            env = "Environment=K230_TRACE_ID=%s\nEnvironment=K230_TRACE_SECONDS=%d\nEnvironment=K230_TRACE_PATH=%s\n" % (
                trace_id, a.trace_seconds, trace)
            if a.mode == "counters":
                env += "Environment=K230_TRACE_COUNTERS_ONLY=1\n"
        dropin.write_text("[Service]\n" + env + "ExecStart=\nExecStart=%s --serve\n" % wrapper)
        call(["systemd-run", "--unit=" + TIMER, "--on-active=%ds" % a.restore_s, str(cleanup)])
        call(["systemctl", "daemon-reload"])
        call(["systemctl", "restart", "theme-helper", "shell-ui"], timeout=90)
        time.sleep(5)
        for unit in ("shell-ui", "theme-helper", "shell"):
            assert call(["systemctl", "is-active", unit]).strip() == "active", unit
        call(SH + [str(wrapper), "--surface", "settings"], timeout=30)
        time.sleep(3)
        if a.workload in ("gestures", "visible", "video"):
            meta["capture_started_utc"] = now()
            try:
                {"gestures": gesture_session, "visible": visible_session, "video": video_session}[a.workload](a, out, device, state_root, troot)
                meta["capture_rc"] = 0
            except Exception as error:
                meta["capture_rc"] = 1
                meta["error"] = str(error)
                print("GESTURE_FAILED", error, flush=True)
            meta["capture_ended_utc"] = now()
        else:
            listing = json.loads(call(["/run/current-system/sw/bin/k230-theme", "list"], timeout=60))
            gen = str((Path(state_root) / "active").resolve(strict=True))
            report = json.loads((Path(gen) / "report.json").read_text())
            exes = {u: os.readlink("/proc/%s/exe" % call(["systemctl", "show", u, "-p", "MainPID", "--value"]).strip())
                    for u in ("shell-ui", "shell", "theme-helper")}
            plan = {"schema": "k230-theme-picker-profile-plan-v1", "label": "baseline" if a.kind == "baseline" else "candidate",
                    "device": device, "state_root": state_root,
                    "settings_ready": True, "geometry": {"width": 568, "height": 1232},
                    "background_playback": a.playback, "first_opening": "process-cold",
                    "instrumentation": a.mode, "attribution": True, "max_process_age_s": 600,
                    "selected_theme_id": a.selected_label,
                    "rows": {"themes": {"count": len(listing["themes"]), "resolved": True, "visually_reviewed": True},
                             "backgrounds": {"count": len(report["backgrounds"]), "resolved": True, "visually_reviewed": True}},
                    "expect": {"rust_exe": a.exe, "compositor_exe": exes["shell"], "helper_exe": exes["theme-helper"],
                               "generation_sha256": hashlib.sha256(gen.encode()).hexdigest()}}
            (out / "plan.json").write_text(json.dumps(plan, indent=2))
            raw = out / "raw.private.json"
            if raw.exists():
                raw.unlink()
            meta["capture_started_utc"] = now()
            cap = subprocess.run([sys.executable, str(HERE / "theme-picker-profile.py"), "capture", "--plan", str(out / "plan.json"),
                                  "--output", str(raw)], capture_output=True, text=True, timeout=300)
            meta["capture_ended_utc"] = now()
            meta["capture_rc"] = cap.returncode
            print("CAPTURE_RC", cap.returncode, cap.stdout.strip()[-200:], cap.stderr.strip()[-600:], flush=True)
        if a.mode != "off":
            deadline = time.monotonic() + a.trace_seconds + 30
            complete = False
            while time.monotonic() < deadline:
                try:  # the file is serialized after the window; wait for a parseable whole
                    if trace.exists() and trace.stat().st_size:
                        json.loads(trace.read_text())
                        complete = True
                        break
                except ValueError:
                    pass
                time.sleep(0.5)
            if complete:
                (out / "rust-trace.json").write_bytes(trace.read_bytes())
            else:
                print("NO_TRACE", flush=True)
        (out / "meta.json").write_text(json.dumps(meta, indent=2))
    finally:
        restore()
        subprocess.run(["systemctl", "stop", TIMER + ".timer", TIMER + ".service"], check=False, capture_output=True)
    time.sleep(6)
    print("RESTORED", [call(["systemctl", "is-active", u]).strip() for u in ("shell", "shell-ui", "theme-helper")], flush=True)
    print("RUST_EXE_NOW", os.readlink("/proc/%s/exe" % call(["systemctl", "show", "shell-ui", "-p", "MainPID", "--value"]).strip()), flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("input-up")
    r = sub.add_parser("run")
    r.add_argument("--label", required=True)
    r.add_argument("--kind", choices=["baseline", "candidate"], required=True)
    r.add_argument("--exe", required=True)
    r.add_argument("--mode", choices=["off", "counters", "trace"], required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--trace-seconds", type=int, default=110)
    r.add_argument("--restore-s", type=int, default=260)
    r.add_argument("--playback", default="static")
    r.add_argument("--workload", choices=["profile", "gestures", "visible", "video"], default="profile")
    r.add_argument("--row", choices=["theme", "background"], default="theme")
    r.add_argument("--reps", type=int, default=2)
    r.add_argument("--settle", type=float, default=2.5)
    r.add_argument("--selected-label", default="catppuccin")
    a = ap.parse_args()
    if a.cmd == "input-up":
        input_up()
    else:
        run(a)


if __name__ == "__main__":
    main()
