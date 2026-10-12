#!/usr/bin/env python3
"""Pooled observer-cost summary for task 13.2/13.4 (host).

  overhead_pooled.py REPORT_DIR OUT.json

OFF runs ov-off{,2,3}, COUNTERS runs ov-counters{,2,3}, TRACE run ov-trace; same installed ELF, same workload,
fresh service restart before each. Reports medians of per-run pooled figures, with every run's figure kept.
"""
import importlib.util
import json
import statistics
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("summarize", Path(__file__).with_name("summarize.py"))
summ = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summ)

SETS = {"off": ["ov-off", "ov-off2", "ov-off3"], "counters": ["ov-counters", "ov-counters2", "ov-counters3"], "trace": ["ov-trace"]}
FIELDS = [("theme_cold", "gap_median_ms"), ("theme_cold", "rust_cpu_percent"), ("theme_warm", "gap_median_ms"),
          ("theme_warm", "gap_p95_ms"), ("theme_warm", "rust_cpu_percent"), ("background", "gap_median_ms"),
          ("background", "gap_p95_ms"), ("background", "rust_cpu_percent"), ("idle", "rust_cpu_percent"),
          ("idle", "helper_cgroup_cpu_percent"), ("open", "rust_cpu_percent")]


def main(rep_dir, out):
    rows = {mode: [summ.summarize(str(Path(rep_dir) / (n + ".json"))) for n in names] for mode, names in SETS.items()}
    result = {"runs": {}, "median": {}, "delta_vs_off": {}}
    for mode, runs in rows.items():
        result["runs"][mode] = []
        for r in runs:
            row = {f"{g}_{k}": r["groups"][g][k] for g, k in FIELDS}
            row.update(rss_last_mib=r["rss_last_mib"], rss_growth_mib=r["rss_growth_mib"], file=Path(r["file"]).name,
                       gates=r["failures"])
            result["runs"][mode].append(row)
        keys = [k for k in result["runs"][mode][0] if isinstance(result["runs"][mode][0][k], (int, float))]
        result["median"][mode] = {k: round(statistics.median(x[k] for x in result["runs"][mode]), 3) for k in keys}
    for mode in ("counters", "trace"):
        result["delta_vs_off"][mode] = {k: round(result["median"][mode][k] - result["median"]["off"][k], 3) for k in result["median"]["off"]}
        result["delta_vs_off"][mode + "_percent"] = {k: round(100 * (result["median"][mode][k] - result["median"]["off"][k]) / result["median"]["off"][k], 1)
                                                      for k in result["median"]["off"] if result["median"]["off"][k]}
    Path(out).write_text(json.dumps(result, indent=1) + "\n")


if __name__ == "__main__":
    main(*sys.argv[1:3])
