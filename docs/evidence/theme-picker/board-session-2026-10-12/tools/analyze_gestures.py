#!/usr/bin/env python3
"""Injected-gesture timing for task 18.3 (host).

  analyze_gestures.py RUNS_DIR OUT_DIR

Reads runs named g-{mo,ca}-{theme,bg}-{1,2} (mo = motion baseline si9vd, ca = installed candidate), each with
gestures.private.json (injected input schedule and window times), rust-trace.json (event ring) and shots/.
The shell records NO per-frame carousel position, so no position or velocity curve is derived here. What is
measured, per gesture: frame commits (CLOCK_MONOTONIC) relative to the first touch-down, the gaps between them,
release-to-last-commit time, and the injected finger path. Writes gesture-summary.json, gesture-timelines.png and
a label-strip contact sheet per build and row (final selected item is read from the native stills by eye).
"""
import json
import statistics
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

GESTURES = ("flick", "slow", "hold-release", "reversal", "interrupt")
BUILD = {"mo": "motion baseline (si9vd, pre-18.2)", "ca": "installed candidate (ybpn, 18.2)"}
COLOR = {"mo": "#c8553d", "ca": "#2a6f97"}
ROWS = ("theme", "bg")


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))] if v else None


def analyse(run: Path):
    d = json.loads((run / "gestures.private.json").read_text())
    t = json.loads((run / "rust-trace.json").read_text())
    ev = t["events"]
    commits = sorted(e["start_us"] / 1e6 for e in ev if e["kind"] == "commit")
    presented = sorted(e["start_us"] / 1e6 for e in ev if e["kind"] == "presented")
    out = []
    for r in d["records"]:
        t0 = r["down_s"][0]
        last_up = r["up_s"][-1]
        c = [x - t0 for x in commits if t0 - 0.05 <= x <= r["end_s"]]
        p = [x - t0 for x in presented if t0 - 0.05 <= x <= r["end_s"]]
        gaps = [1000 * (b - a) for a, b in zip(c, c[1:])]
        after = [x for x in c if x > last_up - t0]
        out.append({
            "gesture": r["gesture"], "rep": r["rep"], "row": r["row"], "touch_down_to_last_up_ms": round(1000 * (last_up - t0)),
            "commits": len(c), "commits_after_last_up": len(after),
            "last_commit_after_last_up_ms": round(1000 * (c[-1] - (last_up - t0))) if after else 0,
            "first_commit_after_down_ms": round(1000 * c[0]) if c else None,
            "commit_gap_median_ms": round(statistics.median(gaps), 1) if gaps else None,
            "commit_gap_p95_ms": round(pct(gaps, .95), 1) if gaps else None, "commit_gap_max_ms": round(max(gaps), 1) if gaps else None,
            "presented_after_last_up": sum(1 for x in p if x > last_up - t0),
            "generation_unchanged": r["generation_unchanged"], "identities_unchanged": r["identities_unchanged"],
            "_commits_s": c, "_moves": [(m[0] - t0, m[1]) for m in r["moves"]], "_up": [u - t0 for u in r["up_s"]],
        })
    return out, {"events": len(ev), "dropped": t["dropped"]}


def main(runs_dir, out_dir):
    runs_dir, out_dir = Path(runs_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data, summary = {}, {"runs": {}, "table": []}
    for b in BUILD:
        for row in ROWS:
            for rep_run in (1, 2):
                name = f"g-{b}-{row}-{rep_run}"
                if (runs_dir / name / "gestures.private.json").exists():
                    data[(b, row, rep_run)], info = analyse(runs_dir / name)
                    summary["runs"][name] = info
    for (b, row, run), recs in data.items():
        for r in recs:
            summary["table"].append({**{k: v for k, v in r.items() if not k.startswith("_")}, "build": b, "row": row, "run": run})
    # medians per build/row/gesture over the two reps of the two runs
    med = {}
    for b in BUILD:
        for row in ROWS:
            for g in GESTURES:
                rows = [x for x in summary["table"] if x["build"] == b and x["row"] == row and x["gesture"] == g]
                if not rows:
                    continue
                med[f"{b}/{row}/{g}"] = {"n": len(rows), **{k: statistics.median(x[k] for x in rows if x[k] is not None) for k in
                                                           ("commits", "commits_after_last_up", "last_commit_after_last_up_ms", "first_commit_after_down_ms",
                                                            "commit_gap_median_ms", "commit_gap_p95_ms", "commit_gap_max_ms")}}
    summary["median_over_repetitions"] = med
    (out_dir / "gesture-summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    # timelines: one panel per row x gesture; first repetition of the first run of each build
    fig, axes = plt.subplots(2, 5, figsize=(17, 6.4), sharey=False)
    for i, row in enumerate(ROWS):
        for j, g in enumerate(GESTURES):
            ax = axes[i][j]
            for b in BUILD:
                recs = [r for r in data.get((b, row, 1), []) if r["gesture"] == g and r["rep"] == 0]
                if not recs:
                    continue
                r = recs[0]
                start = 0
                for k, up in enumerate(r["_up"]):  # one segment per touch, so a re-touch is not joined to the first
                    seg = [m for m in r["_moves"] if start <= m[0] <= up + 0.0005 and (k == 0 or m[0] > r["_up"][k - 1])]
                    ax.plot([m[0] for m in seg], [m[1] for m in seg], color="#777", lw=1, alpha=0.7,
                            label="injected finger x" if b == "mo" and k == 0 else None)
                    start = up
                off = 590 if b == "mo" else 610
                ax.vlines(r["_commits_s"], off, off + 20, color=COLOR[b], lw=1.3, label=f"commits: {BUILD[b]}" if i == 0 and j == 0 else None)
                for u in r["_up"]:
                    ax.axvline(u, color="#999", ls=":", lw=0.8)
            ax.set_title(f"{row} row: {g}", fontsize=10)
            ax.set_xlim(-0.05, 2.7)
            ax.set_ylim(130, 640)
            if i == 1:
                ax.set_xlabel("s since touch-down")
            if j == 0:
                ax.set_ylabel("injected finger x (px)")
    h, l = axes[0][0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=9, frameon=False)
    fig.suptitle("Injected finger path and frame commits (carousel position is not recorded by the shell, so no position curve is shown)", fontsize=11)
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    fig.savefig(out_dir / "gesture-timelines.png", dpi=80)
    # release-to-last-commit comparison
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.6))
    for i, row in enumerate(ROWS):
        ax = axes[i]
        for k, b in enumerate(BUILD):
            vals = [med.get(f"{b}/{row}/{g}", {}).get("last_commit_after_last_up_ms", 0) for g in GESTURES]
            ax.bar([x + (k - 0.5) * 0.38 for x in range(5)], vals, width=0.36, color=COLOR[b], label=BUILD[b])
        ax.set_xticks(range(5))
        ax.set_xticklabels(GESTURES, fontsize=8)
        ax.set_title(f"{row} row: last commit after final release (median of repetitions)", fontsize=9)
        ax.set_ylabel("ms")
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "gesture-release-to-rest.png", dpi=80)
    # label contact sheets
    for b in BUILD:
        for row in ROWS:
            strips = []
            for run in (1, 2):
                for r in data.get((b, row, run), []):
                    n = len(strips)
                    png = next(iter((runs_dir / f"g-{b}-{row}-{run}" / "shots").glob(f"g{(r['rep'] * 5 + GESTURES.index(r['gesture'])):02d}-*.png")), None)
                    if png is None:
                        continue
                    im = Image.open(png).convert("RGB")
                    w, h = im.size
                    y0, y1 = (int(h * 0.62), int(h * 0.70)) if row == "theme" else (int(h * 0.92), int(h * 0.99))
                    strip = im.crop((0, y0, w, y1))
                    cap = Image.new("RGB", (w, strip.size[1] + 14), (20, 20, 20))
                    cap.paste(strip, (0, 14))
                    ImageDraw.Draw(cap).text((2, 1), f"run{run} {r['gesture']} r{r['rep']}", fill=(255, 220, 120))
                    strips.append(cap)
            if strips:
                cols = 4
                rows_n = (len(strips) + cols - 1) // cols
                sw, sh = strips[0].size
                sheet = Image.new("RGB", (cols * sw + (cols - 1) * 6, rows_n * sh + (rows_n - 1) * 6), (60, 60, 60))
                for k, s in enumerate(strips):
                    sheet.paste(s, ((k % cols) * (sw + 6), (k // cols) * (sh + 6)))
                sheet.save(out_dir / f"labels-{b}-{row}.png")


if __name__ == "__main__":
    main(*sys.argv[1:3])
