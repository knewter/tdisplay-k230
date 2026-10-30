"""Host-side controller for the Qt Quick board stage.

Operator protocol (see docs/evidence/qtquick/README.md): the controller takes the
host board lock (`/tmp/k230-board.lock`) separately for each arm (about two
minutes), so other agents interleave; it never reboots, never changes the boot
default and never stops `shell`. The on-board runner keeps its own deadline,
RuntimeMaxSec and guard timer.
"""
import datetime as dt
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qtquick_analysis as qa  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path.home() / "tmp/k230-coordination/ssh_config.private"
SSH = ["ssh", "-F", str(CONFIG), "-o", "ConnectTimeout=15", "k230"]
LOCK = "/tmp/k230-board.lock"
REMOTE = "/var/tmp/qtq"
APP_IDS = {"qt": "qtquick-software-probe", "baseline": "qtquick-shm-baseline"}


def ssh(command, timeout=120, stdin=None):
    return subprocess.run(SSH + [command], text=True, capture_output=True, timeout=timeout, input=stdin)


def locked(command, timeout):
    """Run a local command holding the host board lock; the lock is released on return."""
    return subprocess.run(["flock", "-w", "900", LOCK] + command, text=True, capture_output=True, timeout=timeout)


def python_path():
    out = ssh("ls -d /nix/store/*python3-riscv64*/bin/python3 | head -1").stdout.strip()
    if not out.endswith("/bin/python3"):
        raise RuntimeError("no python3 in the board system closure")
    return out


def copy_closure(path):
    env = {"NIX_SSHOPTS": f"-F {CONFIG}", "PATH": "/usr/bin:/bin:/run/current-system/sw/bin"}
    import os
    full = dict(os.environ, **env)
    res = subprocess.run(["nix", "copy", "--to", "ssh://k230", path], text=True, capture_output=True,
                         timeout=1800, env=full)
    if res.returncode:
        raise RuntimeError(f"nix copy {path} failed: {res.stderr[-300:]}")


def upload_runner():
    ssh(f"install -d -m 0755 {REMOTE}")
    src = (ROOT / "tools/qtquick_board_runner.py").read_text()
    res = ssh(f"cat > {REMOTE}/runner.py && chmod 0755 {REMOTE}/runner.py", stdin=src)
    if res.returncode:
        raise RuntimeError("runner upload failed")


def make_spec(manifest, toolkit, pair, order, **over):
    art = manifest["artifacts"][toolkit]
    wl = manifest["workload"]
    spec = {"id": f"qtq-{manifest['hash'][:8]}-p{pair}{order}-{toolkit}", "toolkit": toolkit, "pair": pair,
            "order": order, "manifest_hash": manifest["hash"], "artifact": art["store_path"],
            "app_id": APP_IDS[toolkit], "binary": f"{art['store_path']}/{art['binary']}",
            "idle_s": wl["idle_s"], "active_s": wl["active_s"],
            "exit_after_s": wl["idle_s"] + wl["active_s"] + 70, "deadline_s": wl["idle_s"] + wl["active_s"] + 150,
            "startup_timeout_s": 40}
    spec.update(over)
    return spec


def run_remote(py, kind, spec, out_dir, label):
    """Upload the spec, run one arm under the board lock, pull the results back."""
    spec_path = f"{REMOTE}/{spec['id']}.spec.json"
    ssh(f"cat > {spec_path}", stdin=json.dumps(spec))
    remote = f"{shlex.quote(py)} {REMOTE}/runner.py {kind} --spec {spec_path}"
    t0 = time.time()
    res = locked(SSH + [remote], timeout=int(spec["deadline_s"]) + 120)
    outcome = {"label": label, "id": spec["id"], "kind": kind, "returncode": res.returncode,
               "wall_s": round(time.time() - t0, 1), "stdout": res.stdout.strip()[-400:],
               "stderr": res.stderr.strip()[-300:], "utc": dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%SZ")}
    # Pull the run directory (small: JSON, JSONL, PNG captures) as a tar stream.
    pull = subprocess.run(SSH + [f"tar -C {REMOTE} -cf - {spec['id']}"], capture_output=True, timeout=240)
    dest = out_dir / "raw"
    dest.mkdir(parents=True, exist_ok=True)
    if pull.returncode == 0 and pull.stdout:
        subprocess.run(["tar", "-C", str(dest), "-xf", "-"], input=pull.stdout, check=True)
    verify = ssh(f"{shlex.quote(py)} {REMOTE}/runner.py verify --id {spec['id']}")
    outcome["verify"] = verify.stdout.strip()[-300:]
    return outcome


def gates_from_captures(run, raw_dir, identity=None):
    """Decide the visual/interaction gates from the pulled native captures (host-side, PIL)."""
    from PIL import Image
    caps = {c["name"]: c for c in run.get("captures", []) if c.get("file")}

    def load(name):
        c = caps.get(name)
        return (Image.open(raw_dir / c["file"]).convert("RGB"), c["window"]) if c else (None, None)

    def near(a, b, tol=14):
        return all(abs(x - y) <= tol for x, y in zip(a, b))

    gates = {}
    img, win = load("a0-startup")
    if img and win:
        ox, oy = win["x"], win["y"]
        probes = {(10, 10): (0x26, 0x34, 0x4c), (3, 300): (0x16, 0x1b, 0x28), (790, 480): (0xff, 0x5b, 0x79),
                  (640, 250): (0xf9, 0xc6, 0x7a), (40, 105): (0x31, 0x41, 0x5d)}
        hits = {k: near(img.getpixel((ox + k[0], oy + k[1])), v) for k, v in probes.items()
                if ox + k[0] < img.width and oy + k[1] < img.height}
        gates["pixels_correct"] = len(hits) == len(probes) and all(hits.values())
        gates["_pixel_probe"] = {f"{k[0]},{k[1]}": v for k, v in hits.items()}
        lum = sum(1 for x in range(ox + 300, ox + 900, 2) for y in range(oy + 20, oy + 60)
                  if sum(img.getpixel((x, y))) > 600)
        gates["readable"] = lum > 300
    f0, w0 = load("f0-initial")
    f1, _ = load("f1-after-row-tap")
    f2, _ = load("f2-after-scroll")
    f3, _ = load("f3-after-interrupt")
    f4, _ = load("f4-field-focused")
    f5, _ = load("f5-after-keys")
    if f1 and w0:
        ox, oy = w0["x"], w0["y"]
        gates["tap"] = near(f1.getpixel((ox + 40, oy + 105)), (0x4b, 0x6e, 0xa8), 16)
    if f1 and f2 and w0:
        ox, oy = w0["x"], w0["y"]
        diff = sum(1 for x in range(ox + 30, ox + 590, 4) for y in range(oy + 100, oy + 540, 4)
                   if f1.getpixel((x, y)) != f2.getpixel((x, y)))
        gates["scroll"] = diff > 400
    if f3 and w0:
        ox, oy = w0["x"], w0["y"]
        # interrupted: the retargeted rect ends back at its resting position, full colour
        gates["interrupted_motion"] = near(f3.getpixel((ox + 640, oy + 250)), (0xf9, 0xc6, 0x7a), 16) and \
            near(f3.getpixel((ox + 1060, oy + 250)), (0x16, 0x1b, 0x28), 16)
    if f3 and f4 and w0:
        raw = run.get("functional_raw", {})
        osk_diff = sum(1 for x in range(0, f4.width, 8) for y in range(f4.height - 230, f4.height, 8)
                       if f3.getpixel((x, y)) != f4.getpixel((x, y)))
        gates["text_focus"] = bool(raw.get("osk_visible_after_focus")) and osk_diff > 200
        gates["_osk_diff_samples"] = osk_diff
    if f4 and f5 and w0:
        ox, oy = w0["x"], w0["y"]
        diff = sum(1 for x in range(ox + 640, ox + 1200) for y in range(oy + 100, oy + 180)
                   if f4.getpixel((x, y)) != f5.getpixel((x, y)))
        gates["text_entry"] = diff > 150
        gates["_text_entry_pixels"] = diff
    if identity:
        gates["software_route"] = identity.get("software_route")
    return gates


def identity_verdict(ident, toolkit):
    """Software/SHM route from the WAYLAND_DEBUG identity run."""
    if not ident.get("ok"):
        return None
    shm = ident.get("attach_count", 0) > 0 and ident.get("create_buffer_formats")
    no_gpu_buffers = ident.get("linux_dmabuf_requests", 0) == 0 and ident.get("wl_drm_requests", 0) == 0
    if toolkit == "baseline":
        return bool(shm and no_gpu_buffers)
    env = ident.get("effective_env", {})
    software = env.get("QT_QUICK_BACKEND") == "software" and env.get("QT_QPA_PLATFORM") == "wayland" \
        and not ident.get("qsg_rhi_backend_inherited")
    qsg = " ".join(ident.get("qsg_info_lines", []) + ident.get("qsg_info_in_stderr", [])).lower()
    hardware_named = any(w in qsg for w in ("opengl", "vulkan", "metal", "d3d"))
    return bool(software and shm and no_gpu_buffers and not hardware_named)


def orchestrate(manifest, stage, out_dir):
    if stage != "qt":
        print("only the Qt stage is implemented in this controller; the Quickshell stage is gated", file=sys.stderr)
        return 3
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "runs").mkdir(exist_ok=True)
    (out_dir / "restoration").mkdir(exist_ok=True)
    py = python_path()
    ident = ssh("readlink /run/current-system; cat /proc/sys/kernel/random/boot_id; cat /sys/class/power_supply/*/online 2>/dev/null | head -3; uptime").stdout.splitlines()
    current = ident[0] if ident else ""
    if current != manifest["system"]["toplevel"]:
        print(f"board system {current} differs from the manifest {manifest['system']['toplevel']}; refusing", file=sys.stderr)
        return 4
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    for toolkit in qa.TOOLKITS:
        copy_closure(manifest["artifacts"][toolkit]["store_path"])
    upload_runner()
    log = []
    identities = {}
    for toolkit in qa.TOOLKITS:
        spec = make_spec(manifest, toolkit, 0, 0, deadline_s=60, exit_after_s=20)
        spec["id"] = spec["id"].replace("p00", "ident")
        outcome = run_remote(py, "identity", spec, out_dir, f"identity-{toolkit}")
        log.append(outcome)
        path = out_dir / "raw" / spec["id"] / "identity.json"
        identities[toolkit] = json.loads(path.read_text()) if path.is_file() else {"ok": False}
        (out_dir / f"identity-{toolkit}.json").write_text(json.dumps(identities[toolkit], indent=2) + "\n")
        (out_dir / "restoration" / f"identity-{toolkit}.json").write_text(
            json.dumps(identities[toolkit].get("restoration", {"ok": False}), indent=2) + "\n")
    neg = make_spec(manifest, "qt", 0, 0, mode="negative", deadline_s=60, exit_after_s=30, args=["--negative-effect"])
    neg["id"] = neg["id"].replace("p00", "negctl")
    log.append(run_remote(py, "arm", neg, out_dir, "negative-control"))
    for pair in range(1, qa.WORKLOAD["pairs"] + 1):
        order = ("qt", "baseline") if pair != 2 else ("baseline", "qt")
        for position, toolkit in enumerate(order, 1):
            spec = make_spec(manifest, toolkit, pair, position)
            outcome = run_remote(py, "arm", spec, out_dir, f"pair{pair}-{toolkit}")
            log.append(outcome)
            raw = out_dir / "raw" / spec["id"]
            run_file = raw / "run.json"
            if run_file.is_file():
                run = json.loads(run_file.read_text())
                run["gates"] = gates_from_captures(run, raw, {"software_route": identity_verdict(identities[toolkit], toolkit)})
                for gate in qa.FUNCTIONAL_GATES:
                    if gate in run["gates"] and gate not in ("bounded_lifetime", "restored"):
                        run["functional"][gate] = run["gates"][gate]
                run["functional"]["software_route"] = run["gates"].get("software_route")
                events = raw / "client.jsonl"
                run["events_file"] = f"pair{pair}-{toolkit}.jsonl"
                (out_dir / "runs" / f"pair{pair}-{toolkit}.json").write_text(json.dumps(run, indent=1) + "\n")
                (out_dir / "runs" / run["events_file"]).write_text(events.read_text() if events.is_file() else "")
                (out_dir / "restoration" / f"pair{pair}-{toolkit}.json").write_text(
                    json.dumps(run.get("restoration", {"ok": False}), indent=2) + "\n")
            else:
                (out_dir / "restoration" / f"pair{pair}-{toolkit}.json").write_text(json.dumps({"ok": False, "reason": "no run record"}) + "\n")
            print(f"pair{pair} {toolkit}: rc={outcome['returncode']} {outcome['stdout'][-120:]}")
            time.sleep(8)  # settle between arms, lock released
    (out_dir / "trial-log.json").write_text(json.dumps(log, indent=2) + "\n")
    return 0
