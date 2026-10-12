"""Host fixtures for tools/theme-picker-profile.py (task 13.1). No board I/O."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("theme_picker_profile", ROOT / "tools/theme-picker-profile.py")
tpp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tpp)

H = "a" * 32
RUST = f"/nix/store/{H}-k230-shell-rust-0.1.0/bin/k230-shell-rust"
RUST2 = f"/nix/store/{'b' * 32}-k230-shell-rust-0.1.0/bin/k230-shell-rust"
SWAY = f"/nix/store/{'c' * 32}-sway-unwrapped-1.12/bin/sway"
PY = f"/nix/store/{'d' * 32}-python3-3.14.7/bin/python3.14"
SYSTEM = f"/nix/store/{'e' * 32}-nixos-system-x"
GEN_PATH = "/home/PRIVATE_USER/.local/state/PRIVATE_SECRET_THEME/gen-1"
THEME_ID = "PRIVATE_THEME_NAME"


def good_plan():
    return {
        "schema": tpp.PLAN_SCHEMA, "label": "baseline", "device": "/dev/input/event1",
        "state_root": "/home/PRIVATE_USER/.local/state/omarchy/current", "settings_ready": True,
        "geometry": {"width": 568, "height": 1232}, "background_playback": "static",
        "first_opening": "first-observed", "selected_theme_id": THEME_ID,
        "rows": {"themes": {"count": 23, "resolved": True, "visually_reviewed": True},
                 "backgrounds": {"count": 5, "resolved": True, "visually_reviewed": True}},
        "expect": {"rust_exe": RUST, "compositor_exe": SWAY, "helper_exe": PY,
                   "generation_sha256": tpp.digest(GEN_PATH)},
    }


def ident(unit, pid, exe):
    return {"pid": pid, "exe": exe, "cgroup": "/system.slice/" + unit, "start_ticks": 1000 + pid}


def build_raw(rust_exe=RUST, gaps=(100, 120, 90), foreign_pid=False, activate=False, mix_callbacks=False,
              drop_background_swipe=False, gen_ok=True):
    """Synthetic capture: phases at 10 s spacing, events placed by monotonic time."""
    workload = tpp.default_workload()
    phases, t = [], 100.0
    for step in workload:
        item = {"name": step["name"], "kind": step["kind"], "start_monotonic_s": t}
        if step["kind"] == "open":
            item["opening"] = "first-observed" if not any(p["kind"] == "open" for p in phases) else "warm"
        t += step["seconds"] + 1
        item["end_monotonic_s"] = t - 0.5
        phases.append(item)
    if drop_background_swipe:
        phases = [p for p in phases if p["kind"] != "swipe-background"]
    events, rust_clock = [], 1000

    def add(at, text, pid=77, unit="shell-ui.service"):
        events.append({"monotonic_us": int(at * 1e6), "unit": unit, "pid": pid, "message": text})

    for p in phases:
        if p["kind"] in ("swipe-theme", "swipe-background"):
            at = p["start_monotonic_s"] + 0.1
            rust_clock += 5000
            add(at, f"rust-shell {rust_clock}ms touch-down 10 10 0 0")
            clock = rust_clock
            for g in gaps:
                clock += g
                at += 0.05
                add(at, f"rust-shell {clock}ms commit")
                if mix_callbacks:
                    add(at + 0.01, f"rust-shell {clock + 3}ms frame-done")
                    add(at + 0.01, f"rust-shell {clock + 4}ms wallpaper-commit")
            add(at + 0.01, f"rust-shell {clock + 1}ms touch-up 1")
        elif p["kind"] == "idle":
            rust_clock += 15000
            add(p["start_monotonic_s"] + 5, f"rust-shell {rust_clock}ms commit")
            add(p["start_monotonic_s"] + 12, f"rust-shell {rust_clock + 7000}ms commit")
            rust_clock += 7000
    if foreign_pid:
        add(150, f"rust-shell {rust_clock + 10}ms commit", pid=999)
    if activate:
        add(150, f"rust-shell {rust_clock + 20}ms theme-command activate abc123 path=socket ms=5")
    add(150, f"rust-shell {rust_clock + 30}ms theme-command list - path=socket ms=40", unit="theme-helper.service")
    samples = []
    for i in range(int((t - 100) / 0.5)):
        units = {u: {"ticks": 100 * i + n, "start_ticks": 1000 + pid, "rss_bytes": 90_000_000 + i,
                     "cgroup_cpu": {"usage_usec": 1000 * i}} for n, (u, pid) in enumerate(
                         (("shell-ui.service", 77), ("shell.service", 78), ("theme-helper.service", 79)))}
        samples.append({"monotonic_s": 100 + i * 0.5, "generation_sha256": tpp.digest(GEN_PATH), "units": units})
    return {
        "schema": tpp.RAW_SCHEMA, "label": "baseline", "workload": workload, "geometry": {"width": 568, "height": 1232},
        "background_playback": "static", "selected_theme_id": THEME_ID, "plan_rows_reviewed": True,
        "clock_ticks_per_second": 100, "booted_system": SYSTEM, "current_system": SYSTEM, "kernel_release": "6.6.36",
        "identities": {"shell-ui.service": ident("shell-ui.service", 77, rust_exe),
                       "shell.service": ident("shell.service", 78, SWAY),
                       "theme-helper.service": ident("theme-helper.service", 79, PY)},
        "observed": {"exes": {"shell-ui.service": rust_exe, "shell.service": SWAY, "theme-helper.service": PY},
                     "generation_sha256": tpp.digest(GEN_PATH), "theme_count": 23, "background_count": 5},
        "precondition_failures": [], "phases": phases, "samples": samples, "errors": [], "events": events,
        "status": "CAPTURED_REQUIRES_REVIEW", "generation_unchanged": gen_ok,
        "start_monotonic_s": 100.0, "end_monotonic_s": t,
    }


class PlanTests(unittest.TestCase):
    def test_good_plan_validates(self):
        self.assertEqual(tpp.validate_plan(good_plan()), [])

    def test_missing_or_unreviewed_rows_are_rejected(self):
        plan = good_plan()
        plan["rows"]["backgrounds"]["count"] = 0
        self.assertTrue(any("missing row" in e for e in tpp.validate_plan(plan)))
        plan = good_plan()
        plan["rows"]["themes"]["visually_reviewed"] = False
        self.assertTrue(any("visually_reviewed" in e for e in tpp.validate_plan(plan)))
        plan = good_plan()
        del plan["rows"]["backgrounds"]
        self.assertTrue(any("rows.backgrounds missing" in e for e in tpp.validate_plan(plan)))

    def test_identity_geometry_and_device_rules(self):
        plan = good_plan()
        plan["expect"]["rust_exe"] = "/usr/bin/shell"
        plan["geometry"] = {"width": 800, "height": 600}
        plan["device"] = "/dev/input/mouse0"
        plan["background_playback"] = "maybe"
        joined = " ".join(tpp.validate_plan(plan))
        for word in ("rust_exe", "geometry", "device", "background_playback"):
            self.assertIn(word, joined)

    def test_workload_rules(self):
        plan = good_plan()
        plan["workload"] = [{"name": "idle-x", "kind": "idle", "seconds": 5}]
        errors = " ".join(tpp.validate_plan(plan))
        self.assertIn("idle windows are 15", errors)
        self.assertIn("theme swipe", errors)
        plan["workload"] = [{"name": "idle-x", "kind": "idle", "seconds": 15, "touch": [1, 1]}]
        self.assertIn("cannot inject", " ".join(tpp.validate_plan(plan)))
        plan["workload"] = [{"name": "s", "kind": "swipe-theme", "seconds": 1, "touch": [0, 0, 600, 0]}]
        self.assertIn("outside native panel", " ".join(tpp.validate_plan(plan)))

    def test_default_workload_has_two_15s_idle_windows_and_no_activation_step(self):
        steps = tpp.default_workload()
        self.assertEqual([s["seconds"] for s in steps if s["kind"] == "idle"], [15, 15])
        self.assertEqual(tpp.validate_workload(steps), [])


class OpeningTests(unittest.TestCase):
    def test_first_observed_never_claims_cold(self):
        self.assertEqual(tpp.classify_opening("first-observed", prior_touch_events=9, process_age_s=1e6, max_age_s=1),
                         "first-observed")

    def test_process_cold_requires_verified_young_untouched_process(self):
        ok = dict(prior_touch_events=0, process_age_s=30, max_age_s=600)
        self.assertEqual(tpp.classify_opening("process-cold", **ok), "process-cold")
        for bad in (dict(ok, prior_touch_events=2), dict(ok, process_age_s=601),
                    dict(ok, prior_touch_events=None), dict(ok, process_age_s=None)):
            with self.assertRaises(ValueError):
                tpp.classify_opening("process-cold", **bad)
        with self.assertRaises(ValueError):
            tpp.classify_opening("disk-cold", **ok)


class PreconditionTests(unittest.TestCase):
    def observed(self):
        return {"theme_count": 23, "background_count": 5, "exes": {"shell-ui.service": RUST, "shell.service": SWAY,
                                                                   "theme-helper.service": PY},
                "generation_sha256": tpp.digest(GEN_PATH), "selected_theme_sha256": tpp.digest(THEME_ID)}

    def test_matching_board_passes(self):
        self.assertEqual(tpp.precondition_failures(good_plan(), self.observed()), [])

    def test_each_mismatch_is_reported(self):
        obs = self.observed()
        obs["background_count"] = None
        obs["theme_count"] = 22
        obs["exes"]["shell-ui.service"] = RUST2
        obs["generation_sha256"] = tpp.digest("other")
        obs["selected_theme_sha256"] = tpp.digest("other")
        text = " ".join(tpp.precondition_failures(good_plan(), obs))
        for word in ("backgrounds row missing", "themes count 22", "shell-ui.service executable", "generation", "selected theme"):
            self.assertIn(word, text)

    def test_pid_reuse_and_generation_change_abort(self):
        idents = {"shell-ui.service": {"pid": 77, "start_ticks": 1077}}
        sample = {"units": {"shell-ui.service": {"start_ticks": 1077}}, "generation_sha256": "g"}
        tpp.check_sample(idents, sample, "g")
        with self.assertRaisesRegex(RuntimeError, "PID identity"):
            tpp.check_sample(idents, {"units": {"shell-ui.service": {"start_ticks": 5}}, "generation_sha256": "g"}, "g")
        with self.assertRaisesRegex(RuntimeError, "generation changed"):
            tpp.check_sample(idents, dict(sample, generation_sha256="h"), "g")
        with self.assertRaisesRegex(RuntimeError, "missing"):
            tpp.check_sample(idents, {"units": {}, "generation_sha256": "g"}, "g")


class ReducerTests(unittest.TestCase):
    def test_clean_capture_reduces_and_gaps_are_per_swipe(self):
        report = tpp.reduce_raw(build_raw())
        self.assertTrue(report["comparable_inputs_valid"], report["failures"])
        swipes = [p for p in report["phases"] if p["kind"].startswith("swipe")]
        self.assertEqual(len(swipes), 6 + 4 + 6)
        for p in swipes:
            self.assertEqual(p["commit_gaps_ms"], [120, 90])
            self.assertEqual(p["commit_gap_median_ms"], 105)
        self.assertEqual(report["openings"], ["first-observed", "warm"])

    def test_idle_windows_are_counts_not_gaps(self):
        report = tpp.reduce_raw(build_raw())
        idle = [p for p in report["phases"] if p["kind"] == "idle"]
        self.assertEqual([p["idle_commit_count"] for p in idle], [2, 2])
        for p in idle:
            self.assertNotIn("commit_gaps_ms", p)
            self.assertNotIn("commit_gap_max_ms", p)

    def test_callback_and_wallpaper_events_do_not_enter_swipe_gaps(self):
        plain = tpp.reduce_raw(build_raw())
        mixed = tpp.reduce_raw(build_raw(mix_callbacks=True))
        a = [p["commit_gaps_ms"] for p in plain["phases"] if p["kind"].startswith("swipe")]
        b = [p["commit_gaps_ms"] for p in mixed["phases"] if p["kind"].startswith("swipe")]
        self.assertEqual(a, b)
        self.assertEqual(tpp.swipe_gaps([300, 100, 200]), [100, 100])

    def test_gaps_never_span_phase_boundaries(self):
        raw = build_raw()
        report = tpp.reduce_raw(raw)
        # three commits per swipe -> exactly two gaps; no cross-phase interval (5 s apart) appears
        for p in report["phases"]:
            if p["kind"].startswith("swipe"):
                self.assertLess(max(p["commit_gaps_ms"]), 1000)

    def test_pid_reuse_events_fail_the_run(self):
        report = tpp.reduce_raw(build_raw(foreign_pid=True))
        self.assertFalse(report["comparable_inputs_valid"])
        self.assertTrue(any("different PID" in f for f in report["failures"]))

    def test_rust_clock_regression_is_a_restart(self):
        raw = build_raw()
        raw["events"].append({"monotonic_us": 400_000_000, "unit": "shell-ui.service", "pid": 77,
                              "message": "rust-shell 5ms commit"})
        report = tpp.reduce_raw(raw)
        self.assertTrue(any("went backwards" in f for f in report["failures"]))

    def test_generation_change_and_activation_fail(self):
        self.assertFalse(tpp.reduce_raw(build_raw(gen_ok=False))["comparable_inputs_valid"])
        report = tpp.reduce_raw(build_raw(activate=True))
        self.assertTrue(any("activation" in f for f in report["failures"]))

    def test_missing_swipe_row_phase_fails(self):
        report = tpp.reduce_raw(build_raw(drop_background_swipe=True))
        self.assertTrue(any("swipe-background" in f for f in report["failures"]))

    def test_swipe_without_commits_fails(self):
        report = tpp.reduce_raw(build_raw(gaps=()))
        self.assertFalse(report["comparable_inputs_valid"])

    def test_unexpected_store_identity_is_refused(self):
        raw = build_raw()
        raw["current_system"] = "/home/PRIVATE_USER/system"
        with self.assertRaises(ValueError):
            tpp.reduce_raw(raw)

    def test_report_is_allowlisted_and_hashes_private_identities(self):
        raw = build_raw()
        raw["events"].append({"monotonic_us": 150_000_000, "unit": "shell-ui.service", "pid": 77,
                              "message": "rust-shell 99999999ms secret-token-PRIVATE_TEXT"})
        text = json.dumps(tpp.reduce_raw(raw))
        for private in ("PRIVATE_USER", "PRIVATE_SECRET_THEME", THEME_ID, "PRIVATE_TEXT", GEN_PATH, "/dev/input"):
            self.assertNotIn(private, text)
        self.assertIn(tpp.digest(GEN_PATH), text)
        self.assertIn(tpp.digest(THEME_ID), text)

    def test_rejects_wrong_schema(self):
        with self.assertRaises(ValueError):
            tpp.reduce_raw({"schema": "x"})


class CompareTests(unittest.TestCase):
    def reports(self, **candidate_kwargs):
        return tpp.reduce_raw(build_raw()), tpp.reduce_raw(build_raw(rust_exe=RUST2, **candidate_kwargs))

    def test_matched_runs_with_only_runtime_varying_compare(self):
        a, b = self.reports(gaps=(80, 80, 80))
        result = tpp.compare_reports(a, b)
        self.assertTrue(result["comparable"], result["mismatches"])
        swipe = next(p for p in result["phases"] if p["name"] == "theme-swipe-0")
        self.assertEqual(swipe["commit_gap_median_ms"], {"a": 105, "b": 80})

    def test_same_runtime_still_comparable_by_default(self):
        a = tpp.reduce_raw(build_raw())
        self.assertTrue(tpp.compare_reports(a, a)["comparable"])

    def test_each_content_mismatch_blocks_deltas(self):
        a = tpp.reduce_raw(build_raw())
        cases = {
            "catalog": lambda r: r["observed"].update(background_count=4),
            "generation_sha256": lambda r: r["observed"].update(generation_sha256=tpp.digest("x")),
            "selected_theme_sha256": lambda r: r.update(selected_theme_id="other"),
            "background_playback": lambda r: r.update(background_playback="playing"),
            "geometry": lambda r: r.update(geometry={"width": 1, "height": 1}),
            "kernel_release": lambda r: r.update(kernel_release="6.7"),
        }
        for field, mutate in cases.items():
            raw = build_raw(rust_exe=RUST2)
            mutate(raw)
            result = tpp.compare_reports(a, tpp.reduce_raw(raw))
            self.assertFalse(result["comparable"], field)
            self.assertIn(field + " differs", result["mismatches"])
            self.assertEqual(result["phases"], [])

    def test_opening_history_must_match(self):
        a = tpp.reduce_raw(build_raw())
        raw = build_raw(rust_exe=RUST2)
        raw["phases"][1]["opening"] = "process-cold"
        result = tpp.compare_reports(a, tpp.reduce_raw(raw))
        self.assertIn("openings differs", result["mismatches"])

    def test_compositor_must_match_unless_explicitly_varied(self):
        a = tpp.reduce_raw(build_raw())
        raw = build_raw(rust_exe=RUST2)
        other = f"/nix/store/{'f' * 32}-sway-unwrapped-1.12/bin/sway"
        raw["identities"]["shell.service"]["exe"] = other
        raw["observed"]["exes"]["shell.service"] = other
        b = tpp.reduce_raw(raw)
        self.assertFalse(tpp.compare_reports(a, b)["comparable"])
        self.assertTrue(tpp.compare_reports(a, b, vary=("rust_exe", "compositor_exe", "current_system"))["comparable"])

    def test_failed_report_and_unknown_vary_are_refused(self):
        good = tpp.reduce_raw(build_raw())
        bad = tpp.reduce_raw(build_raw(foreign_pid=True))
        result = tpp.compare_reports(good, bad)
        self.assertFalse(result["comparable"])
        self.assertTrue(any("failed gates" in m for m in result["mismatches"]))
        with self.assertRaises(ValueError):
            tpp.compare_reports(good, good, vary=("kernel_release",))

    def test_unreviewed_rows_are_not_comparable(self):
        a = tpp.reduce_raw(build_raw())
        raw = build_raw(rust_exe=RUST2)
        raw["plan_rows_reviewed"] = False
        result = tpp.compare_reports(a, tpp.reduce_raw(raw))
        self.assertFalse(result["comparable"])


class CliTests(unittest.TestCase):
    def test_validate_reduce_compare_round_trip_with_private_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "plan.json").write_text(json.dumps(good_plan()))
            self.assertEqual(tpp.main(["validate", str(tmp / "plan.json")]), 0)
            for name, exe in (("a", RUST), ("b", RUST2)):
                (tmp / f"{name}.raw.json").write_text(json.dumps(build_raw(rust_exe=exe)))
                self.assertEqual(tpp.main(["reduce", str(tmp / f"{name}.raw.json"), "--output", str(tmp / f"{name}.json")]), 0)
            self.assertEqual(tpp.main(["reduce", str(tmp / "a.raw.json"), "--output", str(tmp / "a.json")]), 2)  # no overwrite
            self.assertEqual(tpp.main(["compare", str(tmp / "a.json"), str(tmp / "b.json")]), 0)
            bad = copy.deepcopy(good_plan())
            bad["rows"]["themes"]["count"] = 0
            (tmp / "bad.json").write_text(json.dumps(bad))
            self.assertEqual(tpp.main(["validate", str(tmp / "bad.json")]), 1)

    def test_source_is_stdlib_only(self):
        source = (ROOT / "tools/theme-picker-profile.py").read_text()
        imports = {line.split()[1].split(".")[0] for line in source.splitlines() if line.startswith(("import ", "from "))}
        self.assertLessEqual(imports, {"argparse", "collections", "hashlib", "json", "os", "re", "statistics",
                                       "struct", "subprocess", "sys", "threading", "time", "pathlib"})


if __name__ == "__main__":
    unittest.main()
