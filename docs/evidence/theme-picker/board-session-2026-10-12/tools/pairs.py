#!/usr/bin/env python3
"""Matched-pair table for tasks 13.4 / 11.3 / 17.3 (host).

  pairs.py REPORT_DIR RUNS_DIR OUT.json

REPORT_DIR holds sanitized `reduce` reports named {tr,of}-pN-{base,cand}.json (tr = trace-mode pairs with the Rust
event ring, of = instrumentation-off pairs); RUNS_DIR holds the private run directories (only read for trace spans).
Writes one JSON with every run's metrics, the per-pair candidate-minus-baseline differences, and medians over pairs.
"""
import importlib.util
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


summ, tph = load("summarize"), load("trace_phases")


def metrics(report: Path, run: Path | None):
    s = summ.summarize(str(report))
    g = s["groups"]
    m = {
        "theme_warm_gap_median_ms": g["theme_warm"]["gap_median_ms"], "theme_warm_gap_p95_ms": g["theme_warm"]["gap_p95_ms"],
        "theme_cold_gap_median_ms": g["theme_cold"]["gap_median_ms"], "theme_cold_gap_p95_ms": g["theme_cold"]["gap_p95_ms"],
        "background_gap_median_ms": g["background"]["gap_median_ms"], "background_gap_p95_ms": g["background"]["gap_p95_ms"],
        "theme_warm_commits": g["theme_warm"]["commits"], "background_commits": g["background"]["commits"],
        "theme_warm_rust_cpu_percent": g["theme_warm"]["rust_cpu_percent"], "theme_cold_rust_cpu_percent": g["theme_cold"]["rust_cpu_percent"],
        "background_rust_cpu_percent": g["background"]["rust_cpu_percent"], "idle_rust_cpu_percent": g["idle"]["rust_cpu_percent"],
        "idle_commits": g["idle"]["commits"],
        "theme_warm_helper_cgroup_cpu_percent": g["theme_warm"]["helper_cgroup_cpu_percent"],
        "theme_cold_helper_cgroup_cpu_percent": g["theme_cold"]["helper_cgroup_cpu_percent"],
        "rss_first_mib": s["rss_first_mib"], "rss_last_mib": s["rss_last_mib"], "rss_growth_mib": s["rss_growth_mib"],
        "rss_peak_mib": s["rss_peak_mib"], "helper_rss_last_mib": s["helper_rss_last_mib"],
        "preview_requests": s["theme_commands"]["preview"], "overlay_prerender_completions": s["speculative_prerender_completions"],
        "overlay_prerender_completions_touch_held": s["speculative_completions_while_touch_held"],
        "generation_unchanged": s["generation_unchanged"], "gates_failed": s["failures"],
    }
    if run is not None and (run / "rust-trace.json").exists():
        t = tph.analyse(run)
        m["trace_events"], m["trace_dropped"] = t["events"], t["dropped"]
        for grp in ("theme_cold", "theme_warm", "background"):
            tg = t["groups"][grp]
            m[grp + "_presented_gap_median_ms"] = tg.get("presented_gaps", {}).get("median_ms")
            m[grp + "_presented_gap_p95_ms"] = tg.get("presented_gaps", {}).get("p95_ms")
            sp = tg["spans"]
            for kind in ("render_total", "scene_rebuild", "picker_row_repaint", "overlay_draw", "overlay_prerender",
                         "appearance_prepare", "thumbnail_hash", "thumbnail_resolve", "thumbnail_read_cache", "thumbnail_decode"):
                if kind in sp:
                    m[f"{grp}_{kind}_count"] = sp[kind]["count"]
                    m[f"{grp}_{kind}_wall_ms_sum"] = sp[kind]["wall_ms_sum"]
                    m[f"{grp}_{kind}_wall_ms_median"] = sp[kind]["wall_ms_median"]
                    m[f"{grp}_{kind}_cpu_ms_sum"] = sp[kind]["cpu_ms_sum"]
                    m[f"{grp}_{kind}_cpu_ms_off_main_thread"] = sp[kind]["cpu_ms_off_main_thread"]
        m["speculative"] = t["speculative"]
        if s.get("counters"):
            m["gesture_phase_counters"] = {ph: {k: v for k, v in kinds.items() if k in (
                "scene_rebuild", "picker_row_repaint", "render_total", "speculative_admission", "speculative_completion",
                "appearance_prepare", "overlay_prerender", "thumbnail_request", "thumbnail_hash", "thumbnail_resolve", "thumbnail_decode")}
                for ph, kinds in s["counters"].items()}
    return m


def main(rep_dir, runs_dir, out):
    rep_dir, runs_dir = Path(rep_dir), Path(runs_dir)
    result = {"runs": {}, "pairs": {}, "median_over_pairs": {}}
    for kind in ("tr", "of"):
        for p in (1, 2, 3):
            for side in ("base", "cand"):
                name = f"{kind}-p{p}-{side}"
                result["runs"][name] = metrics(rep_dir / (name + ".json"), runs_dir / name if kind == "tr" else None)
    for kind in ("tr", "of"):
        diffs = {}
        for p in (1, 2, 3):
            b, c = result["runs"][f"{kind}-p{p}-base"], result["runs"][f"{kind}-p{p}-cand"]
            d = {k: round(c[k] - b[k], 3) for k in b if isinstance(b[k], (int, float)) and isinstance(c.get(k), (int, float)) and not isinstance(b[k], bool)}
            result["pairs"][f"{kind}-p{p}"] = d
            for k, v in d.items():
                diffs.setdefault(k, []).append(v)
        med = {}
        for side in ("base", "cand"):
            for k in result["runs"][f"{kind}-p1-{side}"]:
                vals = [result["runs"][f"{kind}-p{p}-{side}"].get(k) for p in (1, 2, 3)]
                if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
                    med.setdefault(k, {})[side] = round(statistics.median(vals), 3)
        for k, v in med.items():
            v["delta_of_medians"] = round(v["cand"] - v["base"], 3) if "cand" in v and "base" in v else None
            v["pair_deltas"] = diffs.get(k)
        result["median_over_pairs"][kind] = med
    Path(out).write_text(json.dumps(result, indent=1) + "\n")


if __name__ == "__main__":
    main(*sys.argv[1:4])
