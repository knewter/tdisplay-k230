#!/usr/bin/env python3
"""Per-phase-group span attribution from a private capture and its Rust trace (host).

  trace_phases.py RUN_DIR [RUN_DIR ...]      RUN_DIR holds raw.private.json and rust-trace.json (event ring)

Spans (inclusive wall and thread CPU; kinds must not be summed) are assigned to a harness phase group by their
START time. Presentation gaps are differences between consecutive `presented` events inside one swipe phase (the
recorder's Wayland presentation feedback timestamp, not photons). Output contains only numbers and kind names.
Speculative admissions are classified three ways: inside the injected touch (touch-down to touch-up), inside the
swipe window (touch plus the 1.2 s that follows), and, when the recorder has a gesture phase log, in the
`held`/`moving` gesture phases (exact; the earlier recorder has no phase log).
"""
import json
import statistics
import sys
from pathlib import Path

KINDS = ("scene_rebuild", "picker_row_repaint", "overlay_draw", "render_total", "thumbnail_request", "thumbnail_hash",
         "thumbnail_resolve", "thumbnail_read_cache", "thumbnail_decode", "appearance_prepare", "theme_helper_rpc",
         "overlay_prerender", "speculative_admission", "speculative_completion")
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


def analyse(run: Path):
    raw = json.loads((run / "raw.private.json").read_text())
    trace = json.loads((run / "rust-trace.json").read_text())
    events = trace["events"]
    out = {"run": run.name, "events": len(events), "dropped": trace["dropped"], "counters_only": trace.get("counters_only"),
           "groups": {}}
    phases = [p for p in raw["phases"] if "end_monotonic_s" in p]
    downs = sorted(e["start_us"] / 1e6 for e in events if e["kind"] == "input_down")
    ups = sorted(e["start_us"] / 1e6 for e in events if e["kind"] == "input_up")
    swipe_wins = [(p["start_monotonic_s"], p["end_monotonic_s"]) for p in phases if p["kind"].startswith("swipe")]
    # carousel drags only: a touch that starts inside a swipe phase (taps that open/close the picker are excluded)
    held = [(d, u) for d, u in zip(downs, ups) if any(a <= d < b for a, b in swipe_wins)]
    log = trace.get("phase_log")
    main_tid = next(e["tid"] for e in events if e["kind"] == "trace_start")
    for name, pick in GROUPS.items():
        sel = [p for p in phases if pick(p["name"])]
        if not sel:
            continue
        g = {"phases": len(sel), "window_s": round(sum(p["end_monotonic_s"] - p["start_monotonic_s"] for p in sel), 3)}
        spans = {}
        for k in KINDS:
            rows = [e for e in events if e["kind"] == k and any(p["start_monotonic_s"] <= e["start_us"] / 1e6 < p["end_monotonic_s"] for p in sel)]
            if rows:
                wall = [(e["end_us"] - e["start_us"]) / 1000 for e in rows]
                spans[k] = {"count": len(rows), "wall_ms_sum": round(sum(wall), 1), "wall_ms_median": round(statistics.median(wall), 2),
                            "wall_ms_max": round(max(wall), 1), "cpu_ms_sum": round(sum(e["cpu_us"] for e in rows) / 1000, 1),
                            "cpu_ms_off_main_thread": round(sum(e["cpu_us"] for e in rows if e["tid"] != main_tid) / 1000, 1)}
        g["spans"] = spans
        gaps = []
        for p in sel:
            t = sorted(e["start_us"] / 1000 for e in events if e["kind"] == "presented"
                       and p["start_monotonic_s"] <= e["start_us"] / 1e6 < p["end_monotonic_s"])
            gaps += [b - a for a, b in zip(t, t[1:])]
        if gaps:
            g["presented_gaps"] = {"count": len(gaps), "median_ms": round(statistics.median(gaps), 1), "p95_ms": round(pct(gaps, .95), 1)}
        out["groups"][name] = g
    sw = [p for p in phases if p["kind"].startswith("swipe")]
    adm = [e["start_us"] / 1e6 for e in events if e["kind"] == "speculative_admission"]
    comp = [e["start_us"] / 1e6 for e in events if e["kind"] == "speculative_completion"]
    def inside(ts, wins):
        return sum(1 for t in ts if any(a <= t < b for a, b in wins))
    swin = [(p["start_monotonic_s"], p["end_monotonic_s"]) for p in sw]
    out["speculative"] = {"admissions_total": len(adm), "admissions_inside_touch": inside(adm, held),
                          "admissions_inside_swipe_window": inside(adm, swin),
                          "completions_total": len(comp), "completions_inside_touch": inside(comp, held),
                          "completions_inside_swipe_window": inside(comp, swin)}
    if log:
        ivs, prev_t, prev_p = [], None, "rest"
        for e in log:
            t = e["t_us"] / 1e6
            if prev_t is not None:
                ivs.append((prev_t, t, prev_p))
            prev_t, prev_p = t, e["phase"]
        ivs.append((prev_t if prev_t is not None else 0, 1e18, prev_p))
        def phase_of(t):
            for a, b, ph in ivs:
                if a <= t < b:
                    return ph
            return "rest"
        out["speculative"]["admissions_by_gesture_phase"] = {ph: sum(1 for t in adm if phase_of(t) == ph) for ph in ("rest", "held", "moving")}
        out["speculative"]["completions_by_gesture_phase"] = {ph: sum(1 for t in comp if phase_of(t) == ph) for ph in ("rest", "held", "moving")}
    return out


if __name__ == "__main__":
    print(json.dumps([analyse(Path(p)) for p in sys.argv[1:]], indent=1))
