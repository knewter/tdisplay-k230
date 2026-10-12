#!/usr/bin/env python3
"""Run-level summary of sanitized theme-picker-profile reports (host, no I/O beyond arguments).

  summarize.py REPORT.json [REPORT.json ...]   -> JSON on stdout, one entry per report

Pools the per-swipe commit gaps and CPU samples by phase group. Percentages are thread/process CPU seconds
divided by the sampled wall seconds of the covered windows (about 0.5 s sampling, so a 1.4 s swipe window is
only partly covered). Nothing here is presentation FPS.
"""
import json
import statistics
import sys

GROUPS = {
    "theme_cold": lambda n: n.startswith("theme-swipe-"),
    "theme_warm": lambda n: n.startswith("warm-theme-swipe-"),
    "background": lambda n: n.startswith("background-swipe-"),
    "idle": lambda n: n.startswith("idle-"),
    "open": lambda n: n in ("first-open", "warm-open"),
}


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))] if v else None


def summarize(path):
    r = json.load(open(path))
    out = {"file": path, "label": r["label"], "instrumentation": r["instrumentation"], "rust_exe": r["rust_exe"][-60:],
           "failures": r["failures"], "openings": r["openings"], "generation_unchanged": r["generation_unchanged"],
           "speculative_prerender_completions": r["speculative_prerender_completions"],
           "speculative_completions_while_touch_held": r["speculative_completions_while_touch_held"],
           "theme_commands": {a: sum(1 for c in r["theme_commands"] if c["action"] == a) for a in ("list", "preview", "activate")},
           "groups": {}}
    previews = [c["duration_ms"] for c in r["theme_commands"] if c["action"] == "preview"]
    out["preview_ms_sum"] = sum(previews)
    for name, pick in GROUPS.items():
        phases = [p for p in r["phases"] if pick(p["name"])]
        if not phases:
            continue
        g = {"phases": len(phases)}
        gaps = [x for p in phases for x in p.get("commit_gaps_ms", [])]
        if gaps:
            g.update(commit_gaps=len(gaps), gap_median_ms=statistics.median(gaps), gap_p95_ms=pct(gaps, .95), gap_max_ms=max(gaps))
        g["commits"] = sum(p["events"].get("commit", 0) for p in phases)
        g["touch_moves"] = sum(p["events"].get("touch-move", 0) for p in phases)
        wall = {u: 0.0 for u in ("shell-ui.service", "theme-helper.service")}
        cpu = {"rust_threads": {}, "rust_total_s": 0.0, "helper_cgroup_s": 0.0}
        for p in phases:
            for u, a in p.get("attribution", {}).items():
                wall[u] += a["wall_s"]
                if u == "shell-ui.service":
                    cpu["rust_total_s"] += a["threads_cpu_total_s"]
                    for comm, v in a["threads_cpu"].items():
                        cpu["rust_threads"][comm] = cpu["rust_threads"].get(comm, 0.0) + v["cpu_s"]
                else:
                    cpu["helper_cgroup_s"] += a["cgroup_cpu_s"]
        w = wall["shell-ui.service"]
        if w:
            g["covered_wall_s"] = round(w, 3)
            g["rust_cpu_percent"] = round(100 * cpu["rust_total_s"] / w, 2)
            g["rust_thread_cpu_percent"] = {k: round(100 * v / w, 2) for k, v in sorted(cpu["rust_threads"].items()) if v}
            g["helper_cgroup_cpu_percent"] = round(100 * cpu["helper_cgroup_s"] / wall["theme-helper.service"], 2)
        out["groups"][name] = g
    first = r["phases"][0]["units"]["shell-ui.service"]
    last = r["phases"][-1]["units"]["shell-ui.service"]
    out["rss_first_mib"] = round(first["rss_first_bytes"] / 2**20, 2)
    out["rss_last_mib"] = round(last["rss_last_bytes"] / 2**20, 2)
    out["rss_growth_mib"] = round((last["rss_last_bytes"] - first["rss_first_bytes"]) / 2**20, 2)
    out["rss_peak_mib"] = round(max(p["units"]["shell-ui.service"]["rss_peak_bytes"] for p in r["phases"] if "units" in p) / 2**20, 2)
    out["helper_rss_last_mib"] = round(last and r["phases"][-1]["units"]["theme-helper.service"]["rss_last_bytes"] / 2**20, 2)
    rc = r.get("rust_counters")
    if rc and rc.get("by_gesture_phase"):
        out["counters"] = rc["by_gesture_phase"]
        out["counters_events_complete"] = rc["events_complete"]
    return out


if __name__ == "__main__":
    print(json.dumps([summarize(p) for p in sys.argv[1:]], indent=1))
