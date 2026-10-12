#!/usr/bin/env python3
"""Per-frame carousel position and velocity curves for task 18.3 (host).

  curves.py RUNS_DIR OUT_DIR

Reads runs named g-{theme,bg}-{1,2}, each holding gestures.private.json (injected input schedule,
CLOCK_MONOTONIC) and rust-trace.json (event ring). The shell writes one `carousel` event per committed
frame on the Settings route: data = [frame, theme position, theme velocity, background position,
background velocity, theme_phase * 4 + background_phase], the four values as f64 bits. Position is in
items; velocity is the coast or spring velocity in reference-card px/s (positive = card centres moving
right, i.e. toward index 0), and is 0 under a finger and at rest. Phases: 0 rest, 1 finger, 2 coast,
3 settle.

Writes curves-summary.json, position-curves.png and velocity-curves.png. Every plotted point is a frame
the board committed; nothing is replayed through the host model.
"""
import json
import statistics
import struct
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

GESTURES = ("flick", "slow", "hold-release", "reversal", "interrupt")
ROWS = ("theme", "bg")
PHASES = ("rest", "finger", "coast", "settle")


def f64(bits):
    return struct.unpack("<d", struct.pack("<Q", bits))[0]


def frames(trace):
    out = []
    for e in trace["events"]:
        if e["kind"] != "carousel":
            continue
        d = e["data"]
        out.append({"t": e["start_us"] / 1e6, "frame": d[0],
                    "theme": (f64(d[1]), f64(d[2]), PHASES[d[5] // 4]),
                    "bg": (f64(d[3]), f64(d[4]), PHASES[d[5] % 4])})
    return sorted(out, key=lambda f: f["t"])


def analyse(run, row):
    d = json.loads((run / "gestures.private.json").read_text())
    t = json.loads((run / "rust-trace.json").read_text())
    all_frames = frames(t)
    out = []
    for r in d["records"]:
        t0, last_up = r["down_s"][0], r["up_s"][-1]
        seq = [(f["t"] - t0, *f[row]) for f in all_frames if t0 - 0.05 <= f["t"] <= r["end_s"]]
        if not seq:
            out.append({"gesture": r["gesture"], "rep": r["rep"], "frames": 0})
            continue
        up = last_up - t0
        start = seq[0][1]
        final = seq[-1][1]
        # The shell handles the injected release a frame or two after it is written, so the release is
        # taken from the record itself: the last finger-phase frame of the final touch, then everything
        # after it.
        last_finger = max((k for k, s in enumerate(seq) if s[3] == "finger"), default=None)
        if last_finger is None:
            last_finger = max((k for k, s in enumerate(seq) if s[0] <= up), default=0)
        at_up = seq[last_finger]
        after = seq[last_finger + 1:]
        rest_at = next((s[0] for s in after if s[3] == "rest"), None)
        released_at = after[0][0] if after else up
        direction = (final - at_up[1]) or 1.0
        # Travel beyond the final item against the direction of the post-release motion.
        overshoot = max((((s[1] - final) * (1 if direction > 0 else -1)) for s in after), default=0.0)
        diffs = [(b[1] - a[1]) / (b[0] - a[0]) for a, b in zip(seq, seq[1:]) if b[0] > a[0]]
        out.append({
            "gesture": r["gesture"], "rep": r["rep"], "frames": len(seq), "frames_after_release": len(after),
            "start_item": round(start, 3), "item_at_release": round(at_up[1], 3), "final_item": round(final, 3),
            "items_after_release": round(final - at_up[1], 3),
            "release_velocity_px_s": round(after[0][2], 1) if after else None,
            "phases_after_release": sorted({s[3] for s in after}),
            "release_handled_after_injection_ms": round(1000 * (released_at - up)),
            "rest_after_release_ms": round(1000 * (rest_at - released_at)) if rest_at is not None else None,
            "overshoot_items": round(max(overshoot, 0.0), 4),
            "max_items_per_s": round(max((abs(x) for x in diffs), default=0.0), 2),
            "_seq": seq, "_up": [u - t0 for u in r["up_s"]], "_moves": [(m[0] - t0, m[1]) for m in r["moves"]],
        })
    return out, {"events": len(t["events"]), "dropped": t["dropped"], "carousel_frames": len(all_frames)}


def main(runs_dir, out_dir):
    runs_dir, out_dir = Path(runs_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data, summary = {}, {"runs": {}, "table": []}
    for row in ROWS:
        for n in (1, 2):
            run = runs_dir / f"g-{row}-{n}"
            if (run / "gestures.private.json").exists():
                data[(row, n)], summary["runs"][run.name] = analyse(run, "theme" if row == "theme" else "bg")
    for (row, n), recs in data.items():
        for r in recs:
            summary["table"].append({**{k: v for k, v in r.items() if not k.startswith("_")}, "row": row, "run": n})
    med = {}
    for row in ROWS:
        for g in GESTURES:
            rows = [x for x in summary["table"] if x["row"] == row and x["gesture"] == g and x["frames"]]
            if rows:
                med[f"{row}/{g}"] = {"n": len(rows), "final_items": sorted({x["final_item"] for x in rows}),
                                     **{k: statistics.median(x[k] for x in rows if x[k] is not None)
                                        for k in ("frames_after_release", "items_after_release", "overshoot_items",
                                                  "rest_after_release_ms", "release_handled_after_injection_ms", "max_items_per_s")
                                        if any(x[k] is not None for x in rows)}}
    summary["median_over_repetitions"] = med
    (out_dir / "curves-summary.json").write_text(json.dumps(summary, indent=1) + "\n")

    colors = {0: "#2a6f97", 1: "#c8553d"}
    for name, column, ylabel in (("position", 1, "carousel position (items)"),
                                 ("velocity", 2, "coast/spring velocity (reference px/s)")):
        fig, axes = plt.subplots(2, 5, figsize=(18, 6.8))
        for i, row in enumerate(ROWS):
            for j, g in enumerate(GESTURES):
                ax = axes[i][j]
                for n in (1, 2):
                    for r in data.get((row, n), []):
                        if r["gesture"] != g or not r["frames"]:
                            continue
                        seq = r["_seq"]
                        label = f"run {n} rep {r['rep']}"
                        ax.plot([s[0] for s in seq], [s[column] for s in seq], "-o", ms=2.2, lw=1,
                                color=colors[r["rep"]], alpha=0.9 if n == 1 else 0.45, label=label)
                        for u in r["_up"]:
                            ax.axvline(u, color="#999", ls=":", lw=0.8)
                ax.set_title(f"{row} row: {g}", fontsize=10)
                ax.set_xlim(-0.05, 2.7)
                if i == 1:
                    ax.set_xlabel("s since first touch-down")
                if j == 0:
                    ax.set_ylabel(ylabel, fontsize=9)
        h, l = axes[0][0].get_legend_handles_labels()
        fig.legend(h, l, loc="lower center", ncol=4, fontsize=9, frameon=False)
        fig.suptitle(f"Board-committed carousel {name} per frame (dotted: injected touch-up)", fontsize=11)
        fig.tight_layout(rect=(0, 0.05, 1, 0.95))
        fig.savefig(out_dir / f"{name}-curves.png", dpi=80)


if __name__ == "__main__":
    main(*sys.argv[1:3])
