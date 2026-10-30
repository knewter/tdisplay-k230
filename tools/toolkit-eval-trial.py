#!/usr/bin/env python3
"""Matched-pair board trial for a candidate toolkit client against the shared
wl_shm baseline, reusing the Qt trial's analysis (tools/qtquick_analysis.py).

  toolkit-eval-trial.py --self-test
  toolkit-eval-trial.py board --name egui --candidate STORE_OUT --baseline STORE_OUT --out DIR
  toolkit-eval-trial.py analyse --out DIR

Board runs hold /tmp/k230-board.lock on the host for one arm at a time, start
transient processes only (no system change, no boot-default change) and check the
compositor identity before and after each arm. Evidence class: injected board
input (uinput pointer) plus client commit timestamps; never glass, never optical.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qtquick_analysis as qa  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SSH = ["ssh", "-F", str(Path.home() / "tmp/k230-coordination/ssh_config.private"), "k230"]
SCP = ["scp", "-F", str(Path.home() / "tmp/k230-coordination/ssh_config.private")]
LOCK = "/tmp/k230-board.lock"
REMOTE = "/var/tmp/toolkit-eval"
PY = "$(ls -d /nix/store/*python3-riscv64*/bin/python3 | head -1)"
BIN = {"egui": "bin/egui-software-probe", "baseline": "bin/qtquick-shm-baseline", "sidestep": "bin/sidestep-probe"}
CARD_BUDGETS = {"frame_cpu_p95_ms": 16.667, "tracking_interval_p95_ms": 33.334}


def sh(cmd, **kw):
    return subprocess.run(cmd, text=True, capture_output=True, **kw)


def board_arm(name, binary, out_dir, idle, active, deadline=150):
    """One arm under the board lock; returns the board-side summary line."""
    remote_out = f"{REMOTE}/{out_dir.name}"
    script = (ROOT / "tools/toolkit-eval-board.py").read_text()
    cmd = (f"flock -w 900 {LOCK} {' '.join(SSH)} "
           f"\"{PY} - --bin {binary} --name {name} --out {remote_out} --idle {idle} --active {active} "
           f"--deadline {deadline} --grim\"")
    res = subprocess.run(cmd, shell=True, input=script, text=True, capture_output=True, timeout=deadline + 900)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "board-stdout.txt").write_text(res.stdout + res.stderr)
    sh(SCP + ["-r", f"k230:{remote_out}/.", str(out_dir)])
    return res


def stage(candidate_name, candidate_out, baseline_out):
    for out in (candidate_out, baseline_out):
        env = dict(os.environ, NIX_SSHOPTS="-F " + str(Path.home() / "tmp/k230-coordination/ssh_config.private"))
        r = sh(["nix", "copy", "--to", "ssh://k230", out], env=env)
        if r.returncode:
            raise SystemExit(f"nix copy {out}: {r.stderr}")
    sh(SSH + [f"mkdir -p -m 1777 {REMOTE}"])
    sh(SCP + [str(ROOT / "tools/board-pointer.py"), f"k230:{REMOTE}/board-pointer.py"])


def board(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stage(args.name, args.candidate, args.baseline)
    bins = {args.name: f"{args.candidate}/{BIN[args.name]}", "baseline": f"{args.baseline}/{BIN['baseline']}"}
    for pair in range(1, args.pairs + 1):
        order = (args.name, "baseline") if pair != 2 else ("baseline", args.name)
        for pos, name in enumerate(order, 1):
            d = out / f"pair{pair}-{name}"
            print(f"pair {pair} arm {pos}: {name}", flush=True)
            res = board_arm(name, bins[name], d, args.idle, args.active)
            print(res.stdout.strip()[-300:], flush=True)
            (d / "meta.json").write_text(json.dumps({"pair": pair, "order": pos, "name": name, "binary": bins[name]}))
    return 0


def pct(values, q):
    return qa.percentile(values, q)


def arm_metrics(arm_dir, candidate):
    run = json.loads((arm_dir / "run.json").read_text())
    meta = json.loads((arm_dir / "meta.json").read_text())
    events = qa.parse_events((arm_dir / "events.jsonl").read_text())
    qrun = dict(run)
    qrun.setdefault("phases", {})
    res = qa.analyse_run(qrun, events)
    m = res["metrics"]
    active = run.get("phases", {}).get("active", {})
    window = (active.get("start_mono_ms", 0), active.get("end_mono_ms", 0))
    gaps = qa.commit_gaps(events, window) if window[1] else []
    lat = qa.input_to_commit(events, window) if window[1] else []
    renders = [e["r"] / 1000.0 for e in events if e["e"] == "commit" and "r" in e and window[0] <= e["t"] < window[1]]
    m["commit_gap_p50_ms"] = pct(gaps, 0.5)
    m["commit_gap_p99_ms"] = pct(gaps, 0.99)
    m["input_to_commit_p99_ms"] = pct(lat, 0.99)
    m["commits_in_active"] = len(gaps) + 1 if gaps else 0
    m["render_p50_ms"] = pct(renders, 0.5)
    m["render_p95_ms"] = pct(renders, 0.95)
    m["render_max_ms"] = max(renders) if renders else None
    m["client_pss_active_kib"] = run.get("smaps_active", {}).get("Pss")
    m["client_rss_active_kib"] = run.get("smaps_active", {}).get("Rss")
    restored = bool(run.get("ok")) and bool(run.get("client_gone")) and all(run.get("same_identity", {}).values())
    return {"pair": meta["pair"], "name": meta["name"], "metrics": m, "missing": res["missing"], "restored": restored,
            "ok": run.get("ok"), "error": run.get("error"), "cpu_freq_khz": run.get("cpu_freq_khz"),
            "output": run.get("output")}


def analyse(args):
    out = Path(args.out)
    arms = [arm_metrics(d, args.name) for d in sorted(out.glob("pair*-*")) if (d / "run.json").exists()]
    names = sorted({a["name"] for a in arms})
    candidate = [n for n in names if n != "baseline"]
    summary = {"arms": arms, "restored_all": all(a["restored"] for a in arms)}
    json.dump(summary, open(out / "summary.json", "w"), indent=1)
    keys = ["startup_ms", "incremental_memory_mib", "client_pss_active_kib", "idle_client_cpu_pct", "idle_sway_cpu_pct",
            "active_client_cpu_pct", "active_sway_cpu_pct", "active_combined_cpu_pct", "commit_gap_p50_ms",
            "commit_gap_p95_ms", "commit_gap_max_ms", "commits_in_active", "render_p50_ms", "render_p95_ms",
            "render_max_ms", "input_to_commit_p50_ms", "input_to_commit_p95_ms", "input_samples", "interactions"]
    lines = ["| metric | " + " | ".join(f"{a['name']} #{a['pair']}" for a in arms) + " |",
             "| --- | " + " | ".join("---:" for _ in arms) + " |"]
    for k in keys:
        lines.append(f"| {k} | " + " | ".join("-" if a["metrics"].get(k) is None else f"{a['metrics'][k]:.2f}"
                                               for a in arms) + " |")
    lines.append("| restored | " + " | ".join("yes" if a["restored"] else "NO" for a in arms) + " |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if summary["restored_all"] else 1


class SelfTest(unittest.TestCase):
    def test_arm_metrics_reads_a_run(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "pair1-egui"
            d.mkdir()
            events = [{"e": "start", "t": 100}, {"e": "first_frame", "t": 400}]
            for i in range(30):
                events += [{"e": "input", "t": 10_000 + i * 900, "k": "press"},
                           {"e": "commit", "t": 10_000 + i * 900 + 20, "r": 15000}]
            (d / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
            (d / "meta.json").write_text(json.dumps({"pair": 1, "order": 1, "name": "egui"}))
            (d / "run.json").write_text(json.dumps({
                "ok": True, "client_gone": True, "same_identity": {"system": True}, "launch_mono_ms": 100,
                "phases": {"idle": {"elapsed_s": 30, "client_cpu_us": 300000, "sway_cpu_us": 300000},
                           "active": {"elapsed_s": 30, "client_cpu_us": 6_000_000, "sway_cpu_us": 3_000_000,
                                      "start_mono_ms": 9_000, "end_mono_ms": 40_000}},
                "memory": {"before_kib": 1000, "active_used_kib": 1000 + 20 * 1024},
                "interactions": [{"kind": "press"}] * 30, "smaps_active": {"Pss": 5000, "Rss": 6000}}))
            a = arm_metrics(d, "egui")
            self.assertTrue(a["restored"])
            self.assertEqual(a["metrics"]["startup_ms"], 300)
            self.assertEqual(a["metrics"]["render_p95_ms"], 15.0)
            self.assertAlmostEqual(a["metrics"]["incremental_memory_mib"], 20.0)
            self.assertEqual(a["metrics"]["input_to_commit_p95_ms"], 20)
            self.assertEqual(a["missing"], [])

    def test_missing_events_are_reported_not_invented(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "pair1-egui"
            d.mkdir()
            (d / "events.jsonl").write_text("")
            (d / "meta.json").write_text(json.dumps({"pair": 1, "order": 1, "name": "egui"}))
            (d / "run.json").write_text(json.dumps({"ok": False, "error": "x", "same_identity": {}}))
            a = arm_metrics(d, "egui")
            self.assertFalse(a["restored"])
            self.assertIn("first_frame", a["missing"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("board")
    b.add_argument("--name", required=True, choices=("egui", "sidestep"))
    b.add_argument("--candidate", required=True)
    b.add_argument("--baseline", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--pairs", type=int, default=3)
    b.add_argument("--idle", type=float, default=30)
    b.add_argument("--active", type=float, default=30)
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
