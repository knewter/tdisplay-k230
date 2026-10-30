#!/usr/bin/env python3
"""Opt-in Qt Quick / Quickshell trial: prepare a frozen manifest, run the board
stage, decide. Evidence classes are recorded exactly; see docs/evidence/qtquick/.

  qtquick-trial.py --self-test
  qtquick-trial.py prepare --qt OUT --baseline OUT --output MANIFEST [--system S --compositor C]
  qtquick-trial.py board --manifest MANIFEST --stage qt --output DIR
  qtquick-trial.py decide --stage qt --evidence DIR

Operator commands and the board lock protocol are in docs/evidence/qtquick/README.md.
"""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qtquick_analysis as qa  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SSH = ["ssh", "-F", str(Path.home() / "tmp/k230-coordination/ssh_config.private"), "k230"]


def nix_closure(path):
    """(closure_bytes, closure_paths, nar_bytes) from `nix path-info -rsS`."""
    out = subprocess.run(["nix", "path-info", "-rsS", path], text=True, capture_output=True, check=True).stdout
    rows = [line.split() for line in out.splitlines() if line.strip()]
    root = next((r for r in rows if r[0] == path), None)
    if root is None:
        raise qa.ManifestError(f"{path}: not in `nix path-info` output")
    # columns: path, narSize, closureSize (with -s); the root's closureSize is the unique closure
    return int(root[2]), len(rows), int(root[1])


def artifact_record(name, out_path, closure=nix_closure):
    path = str(out_path)
    if not qa.STORE_RE.match(path):
        raise qa.ManifestError(f"{name}: {path!r} is not a /nix/store output directory")
    binary = Path(path) / qa.BINARIES[name]
    if not binary.is_file():
        raise qa.ManifestError(f"{name}: {binary} is missing")
    closure_bytes, closure_paths, nar = closure(path)
    return {"store_path": path, "binary": qa.BINARIES[name], "closure_bytes": closure_bytes,
            "closure_paths": closure_paths, "nar_bytes": nar}


def board_identity():
    """Read-only identity of the running system and compositor from the board."""
    script = ("readlink /run/current-system; "
              "p=$(pgrep -x sway | head -1); readlink -f /proc/$p/exe; "
              "grep -o '/nix/store/[^ ]*pixman[^ /]*' /proc/$p/maps | sort -u | head -1; "
              "cat /proc/sys/kernel/random/boot_id; "
              "tr ' ' '\\n' </proc/cmdline | grep '^init=' ")
    lines = subprocess.run(SSH + [script], text=True, capture_output=True, check=True, timeout=60).stdout.splitlines()
    if len(lines) < 4:
        raise qa.ManifestError("board identity incomplete")
    import re as _re
    root = _re.match(r"/nix/store/[^/]+", lines[1])
    return {"toplevel": lines[0], "compositor": root.group(0) if root else lines[1], "pixman": lines[2], "boot_default_init": lines[-1]}


def prepare(args, closure=nix_closure, identity=board_identity):
    qt = artifact_record("qt", args.qt, closure)
    baseline = artifact_record("baseline", args.baseline, closure)
    if args.system and args.compositor:
        system = {"toplevel": args.system, "compositor": args.compositor}
    else:
        system = identity()
    source = {"revision": subprocess.run(["git", "rev-parse", "HEAD"], text=True, capture_output=True,
                                         cwd=ROOT).stdout.strip(),
              "workload_id": qa.WORKLOAD_ID, "budget_version": qa.BUDGET_VERSION}
    created = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = qa.build_manifest(created, qt, baseline, system, source)
    qa.validate_manifest(manifest)
    Path(args.output).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"manifest {args.output} hash {manifest['hash'][:16]}")
    return manifest


def load_manifest(path):
    manifest = json.loads(Path(path).read_text())
    return qa.validate_manifest(manifest)


def load_evidence(evidence):
    evidence = Path(evidence)
    manifest = load_manifest(evidence / "manifest.json")
    runs = []
    for run_file in sorted((evidence / "runs").glob("pair*.json")):
        run = json.loads(run_file.read_text())
        events_file = evidence / "runs" / run.get("events_file", "")
        events = qa.parse_events(events_file.read_text()) if run.get("events_file") and events_file.is_file() else []
        runs.append({"run": run, "events": events})
    restorations = [json.loads(p.read_text()) for p in sorted((evidence / "restoration").glob("*.json"))]
    return manifest, runs, restorations


def decide(args):
    if args.stage != "qt":
        # Quickshell is evaluated only after a recorded Qt PASS.
        qt_decision = Path(args.evidence).parent / "qt" / "decision.json"
        if not qt_decision.is_file() or json.loads(qt_decision.read_text()).get("overall") != "PASS":
            print("quickshell stage not run: the Qt prerequisite has no PASS decision", file=sys.stderr)
            return 3
    manifest, runs, restorations = load_evidence(args.evidence)
    decision = qa.evaluate_stage(manifest, runs, restorations)
    decision["stage"] = args.stage
    out = Path(args.evidence) / "decision.json"
    out.write_text(json.dumps(decision, indent=2) + "\n")
    for name, status in decision["criteria"].items():
        print(f"{status:11} {name}")
    for problem in decision["problems"]:
        print("problem:", problem)
    print(f"overall {decision['overall']}  production_budget {decision['production_budget']['status']}")
    return 0 if decision["overall"] == "PASS" else 1


def board(args):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import qtquick_board
    manifest = load_manifest(args.manifest)
    if args.stage != "qt":
        qt_decision = Path(args.output).parent / "qt" / "decision.json"
        if not qt_decision.is_file() or json.loads(qt_decision.read_text()).get("overall") != "PASS":
            print("quickshell board stage refused: the Qt prerequisite has no PASS decision", file=sys.stderr)
            return 3
    return qtquick_board.orchestrate(manifest, args.stage, Path(args.output))


# ---- self test ---------------------------------------------------------------
def _fake_artifact(name, tag):
    return {"store_path": "/nix/store/" + tag * 32 + "-" + name + "-0.1", "binary": qa.BINARIES[name],
            "closure_bytes": 1000, "closure_paths": 3, "nar_bytes": 100}


def _good_manifest():
    return qa.build_manifest("2026-10-30T00:00:00Z", _fake_artifact("qt", "a"), _fake_artifact("baseline", "b"),
                             {"toplevel": "/nix/store/" + "c" * 32 + "-system",
                              "compositor": "/nix/store/" + "d" * 32 + "-sway"}, {"revision": "x"})


def _good_run(manifest, toolkit, pair, order, **over):
    base = 10_000
    events = [{"e": "start", "t": base}, {"e": "first_frame", "t": base + 900}]
    t0 = base + 40_000
    for i in range(30):
        events.append({"e": "input", "t": t0 + i * 900, "k": "press"})
        events.append({"e": "commit", "t": t0 + i * 900 + 25})
    run = {
        "schema": qa.RUN_SCHEMA, "manifest_hash": manifest["hash"], "toolkit": toolkit, "pair": pair,
        "order": order, "artifact": manifest["artifacts"][toolkit]["store_path"], "launch_mono_ms": base,
        "events_file": f"pair{pair}-{toolkit}.jsonl",
        "phases": {"idle": {"elapsed_s": 30, "client_cpu_us": 200_000, "sway_cpu_us": 300_000},
                   "active": {"elapsed_s": 30, "client_cpu_us": 6_000_000, "sway_cpu_us": 3_000_000,
                              "start_mono_ms": t0, "end_mono_ms": t0 + 30_000}},
        "memory": {"before_kib": 300_000, "active_used_kib": 300_000 + 40 * 1024},
        "interactions": [{"kind": "press"}] * 30, "injector_cpu_s": 0.4,
        "functional": {g: True for g in qa.FUNCTIONAL_GATES},
    }
    run.update(over)
    return {"run": run, "events": events}


def _all_runs(manifest, **over_by_toolkit):
    runs = []
    for pair in (1, 2, 3):
        for order, toolkit in enumerate(("qt", "baseline") if pair != 2 else ("baseline", "qt"), 1):
            runs.append(_good_run(manifest, toolkit, pair, order, **over_by_toolkit.get(toolkit, {})))
    return runs


GOOD_RESTORE = [{"ok": True}]


class SelfTest(unittest.TestCase):
    def setUp(self):
        self.manifest = _good_manifest()

    def decide(self, runs, restorations=GOOD_RESTORE, manifest=None):
        return qa.evaluate_stage(manifest or self.manifest, runs, restorations)

    def test_all_good_passes_and_stays_per_run(self):
        d = self.decide(_all_runs(self.manifest))
        self.assertEqual(d["overall"], "PASS")
        self.assertEqual(len(d["runs"]["qt"]), 3)  # per-run records, not pooled
        self.assertEqual(d["production_budget"]["status"], "NOT_ASSESSED")
        self.assertEqual(d["runs"]["qt"][0]["metrics"]["startup_ms"], 900)
        self.assertEqual(d["comparison"]["active_combined_cpu_pct"]["status"], "WITHIN_10_PCT")

    def test_mismatched_ids_are_rejected(self):
        runs = _all_runs(self.manifest)
        runs[0]["run"]["artifact"] = "/nix/store/" + "e" * 32 + "-other"
        d = self.decide(runs)
        self.assertNotEqual(d["overall"], "PASS")
        self.assertTrue(any("artifact id mismatch" in p for p in d["problems"]))
        runs = _all_runs(self.manifest)
        runs[1]["run"]["manifest_hash"] = "0" * 64
        self.assertTrue(any("manifest hash mismatch" in p for p in self.decide(runs)["problems"]))

    def test_missing_presentation_samples_stay_incomplete(self):
        runs = _all_runs(self.manifest)
        for item in runs:
            if item["run"]["toolkit"] == "qt":
                item["events"] = [e for e in item["events"] if e["e"] != "commit"]
        d = self.decide(runs)
        self.assertEqual(d["overall"], "INCOMPLETE")
        self.assertIn("presentation_samples", d["runs"]["qt"][0]["missing"])

    def test_changed_budgets_are_refused(self):
        m = copy.deepcopy(self.manifest)
        m["ceilings"]["startup_ms"] = 9000
        m["hash"] = qa.manifest_hash(m)
        with self.assertRaises(qa.ManifestError):
            qa.validate_manifest(m)
        m = copy.deepcopy(self.manifest)
        m["card_budgets"]["frame_update_cpu_ms"]["p95"] = 99
        m["hash"] = qa.manifest_hash(m)
        with self.assertRaises(qa.ManifestError):
            qa.validate_manifest(m)
        m = copy.deepcopy(self.manifest)
        m["ceilings"]["startup_ms"] = 1  # edited without re-hashing
        with self.assertRaises(qa.ManifestError):
            qa.validate_manifest(m)

    def test_failed_baseline_makes_comparison_inconclusive(self):
        runs = _all_runs(self.manifest, baseline={"functional": {**{g: True for g in qa.FUNCTIONAL_GATES},
                                                                 "scroll": False}})
        d = self.decide(runs)
        self.assertEqual(d["criteria"]["baseline_control"], "FAIL")
        self.assertEqual(d["comparison"]["active_combined_cpu_pct"]["status"], "INCONCLUSIVE")
        self.assertEqual(d["overall"], "FAIL")

    def test_ceiling_failure_is_separate_from_function(self):
        runs = _all_runs(self.manifest, qt={"memory": {"before_kib": 0, "active_used_kib": 200 * 1024}})
        d = self.decide(runs)
        self.assertEqual(d["criteria"]["functional.pixels_correct"], "PASS")
        self.assertEqual(d["criteria"]["ceiling.incremental_memory_mib"], "FAIL")
        self.assertEqual(d["overall"], "FAIL")

    def test_idle_cpu_ceiling_uses_the_client_only(self):
        runs = _all_runs(self.manifest, qt={"phases": {
            "idle": {"elapsed_s": 30, "client_cpu_us": 1_200_000, "sway_cpu_us": 0},
            "active": {"elapsed_s": 30, "client_cpu_us": 6_000_000, "sway_cpu_us": 3_000_000,
                       "start_mono_ms": 50_000, "end_mono_ms": 80_000}}})
        d = self.decide(runs)  # 4% of a core
        self.assertEqual(d["criteria"]["ceiling.idle_client_cpu_pct"], "FAIL")

    def test_regression_over_ten_percent_is_reported_with_variability(self):
        runs = _all_runs(self.manifest, qt={"phases": {
            "idle": {"elapsed_s": 30, "client_cpu_us": 200_000, "sway_cpu_us": 300_000},
            "active": {"elapsed_s": 30, "client_cpu_us": 9_000_000, "sway_cpu_us": 3_000_000,
                       "start_mono_ms": 50_000, "end_mono_ms": 80_000}}})
        row = self.decide(runs)["comparison"]["active_combined_cpu_pct"]
        self.assertEqual(row["status"], "REGRESSION")
        self.assertIn("qt_sd", row)
        self.assertEqual(len(row["pairs"]), 3)

    def test_missing_restoration_or_pairs_is_not_a_pass(self):
        self.assertNotEqual(self.decide(_all_runs(self.manifest), restorations=[])["overall"], "PASS")
        self.assertNotEqual(self.decide(_all_runs(self.manifest)[:4])["overall"], "PASS")

    def test_prepare_rejects_missing_and_mismatched_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(qt="/nix/store/" + "a" * 32 + "-missing", baseline="/tmp/not-store",
                                      output=str(Path(tmp) / "m.json"), system=None, compositor=None)
            with self.assertRaises(qa.ManifestError):
                prepare(args, closure=lambda p: (1, 1, 1), identity=lambda: {})
            args.baseline = args.qt
            with self.assertRaises(qa.ManifestError):
                prepare(args, closure=lambda p: (1, 1, 1), identity=lambda: {})
            self.assertFalse((Path(tmp) / "m.json").exists())

    def test_quickshell_is_gated_on_a_qt_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(manifest="/nonexistent", stage="quickshell",
                                      output=str(Path(tmp) / "quickshell"))
            Path(args.output).mkdir()
            (Path(tmp) / "qt").mkdir()
            (Path(tmp) / "qt/decision.json").write_text(json.dumps({"overall": "FAIL"}))
            # Directly check the gate: decide refuses without a PASS.
            self.assertEqual(decide(argparse.Namespace(stage="quickshell", evidence=args.output)), 3)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--self-test", action="store_true")
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("prepare")
    p.add_argument("--qt", required=True)
    p.add_argument("--baseline", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--system")
    p.add_argument("--compositor")
    b = sub.add_parser("board")
    b.add_argument("--manifest", required=True)
    b.add_argument("--stage", choices=("qt", "quickshell"), required=True)
    b.add_argument("--output", required=True)
    d = sub.add_parser("decide")
    d.add_argument("--stage", choices=("qt", "quickshell"), required=True)
    d.add_argument("--evidence", required=True)
    args = parser.parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(SelfTest)
        return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1
    try:
        if args.cmd == "prepare":
            prepare(args)
            return 0
        if args.cmd == "board":
            return board(args)
        if args.cmd == "decide":
            return decide(args)
    except (qa.ManifestError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    parser.print_help()
    return 64


if __name__ == "__main__":
    sys.exit(main())
