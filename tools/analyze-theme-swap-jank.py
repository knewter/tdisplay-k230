#!/usr/bin/env python3
"""Turn one `tools/theme-swap-jank.py` capture into a pass/fail jank report.

Reads the JSON that tool wrote under `/run/` on the board (copy it off with
`tools/console.py`/`scp`/serial paste), and never opens a board itself --
this half of the pair is host-only, per the "distinct evidence classes"
rule in AGENTS.md. `--self-test` proves the analysis against a synthetic
capture and touches no file the caller did not name.

Frame boundaries come only from the Rust shell's own `commit`/
`wallpaper-commit`/`frame-done` events (nix/rust-shell-client/src/main.rs's
`fn log`); `K230_CARD_SHELL` sway_log lines are kept as timeline context
(what the compositor was doing) but never counted as frames themselves --
sway's default (non-`-d`) log level does not emit a frame-accurate signal
today (see docs/evidence/.../theme-swap-jank/README.md for the follow-up).
"""
import argparse
import json
import sys
import unittest
from pathlib import Path

SCHEMA = "k230-theme-swap-jank-report-v1"
FRAME_EVENTS = {"commit", "wallpaper-commit", "frame-done"}
GAP_THRESHOLDS_MS = (33.0, 50.0, 100.0)
HISTOGRAM_EDGES_MS = (16.7, 33.4, 50.0, 100.0, 200.0, 500.0)
DEFAULT_TARGET_TAP_TO_VISIBLE_MS = 100.0
DEFAULT_MAX_GAP_MS = 100.0


def histogram(deltas_ms: list[float]) -> dict:
    edges = HISTOGRAM_EDGES_MS
    labels = [f"<{edges[0]:.0f}ms"] + [
        f"{edges[i]:.0f}-{edges[i+1]:.0f}ms" for i in range(len(edges) - 1)
    ] + [f">={edges[-1]:.0f}ms"]
    counts = [0] * len(labels)
    for delta in deltas_ms:
        index = 0
        while index < len(edges) and delta >= edges[index]:
            index += 1
        counts[index] += 1
    return dict(zip(labels, counts))


def frame_intervals(events: list[dict], tap_wall_ms: float | None = None) -> list[dict]:
    """Consecutive-frame-event deltas, each tagged with its bounding events.

    When `tap_wall_ms` is given, a synthetic `tap` marker is included as the
    first boundary (never counted as a frame itself) so the stall between
    the user's tap and the first real frame -- exactly the case a slow
    Python start-up or a synchronous decode produces -- shows up as a gap
    like any other, instead of being invisible to the histogram/threshold
    checks and only caught by the separate tap-to-visible check.
    """
    frames = [event for event in events if event.get("event") in FRAME_EVENTS]
    frames.sort(key=lambda event: event["wall_ms"])
    if tap_wall_ms is not None and (not frames or tap_wall_ms < frames[0]["wall_ms"]):
        frames = [{"wall_ms": tap_wall_ms, "event": "tap"}] + frames
    out = []
    for previous, current in zip(frames, frames[1:]):
        out.append({
            "from_event": previous["event"],
            "from_wall_ms": previous["wall_ms"],
            "to_event": current["event"],
            "to_wall_ms": current["wall_ms"],
            "gap_ms": round(current["wall_ms"] - previous["wall_ms"], 2),
        })
    return out


def context_window(events: list[dict], start_ms: float, end_ms: float) -> list[dict]:
    return [event for event in events if start_ms <= event["wall_ms"] <= end_ms]


def analyze(report: dict, target_tap_to_visible_ms: float, max_gap_ms: float) -> dict:
    events = report.get("events") or []
    frame_count = sum(1 for event in events if event.get("event") in FRAME_EVENTS)
    intervals = frame_intervals(events, report.get("tap_wall_ms"))
    deltas = [interval["gap_ms"] for interval in intervals]
    gaps_by_threshold = {}
    for threshold in GAP_THRESHOLDS_MS:
        over = [interval for interval in intervals if interval["gap_ms"] > threshold]
        gaps_by_threshold[f"over_{int(threshold)}ms"] = {
            "count": len(over),
            "gaps": over,
        }
    longest = max(intervals, key=lambda interval: interval["gap_ms"], default=None)
    longest_context = None
    if longest is not None:
        longest_context = {
            **longest,
            "surrounding_events": context_window(
                events, longest["from_wall_ms"] - 5.0, longest["to_wall_ms"] + 5.0
            ),
        }
    tap_wall_ms = report.get("tap_wall_ms")
    visible_wall_ms = report.get("visible_wall_ms")
    tap_to_visible_ms = (
        round(visible_wall_ms - tap_wall_ms, 2)
        if isinstance(tap_wall_ms, (int, float)) and isinstance(visible_wall_ms, (int, float))
        else None
    )
    cpu_samples = report.get("cpu_samples") or []
    failures = []
    if report.get("activation_error"):
        failures.append(f"activation failed: {report['activation_error']}")
    if tap_to_visible_ms is None:
        failures.append("no visible frame observed after tap (wallpaper-commit/commit never seen)")
    elif tap_to_visible_ms > target_tap_to_visible_ms:
        failures.append(
            f"tap-to-visible {tap_to_visible_ms:.1f}ms exceeds target {target_tap_to_visible_ms:.1f}ms"
        )
    over_max = gaps_by_threshold.get(f"over_{int(max_gap_ms)}ms")
    if over_max is None:
        # max_gap_ms may not be one of the three fixed thresholds; compute directly.
        over_max_gaps = [interval for interval in intervals if interval["gap_ms"] > max_gap_ms]
        if over_max_gaps:
            failures.append(f"{len(over_max_gaps)} frame gap(s) exceed {max_gap_ms:.0f}ms")
    elif over_max["count"]:
        failures.append(f"{over_max['count']} frame gap(s) exceed {max_gap_ms:.0f}ms")
    return {
        "schema": SCHEMA,
        "theme_id": report.get("theme_id"),
        "collected_at": report.get("collected_at"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "tap_to_visible_ms": tap_to_visible_ms,
        "target_tap_to_visible_ms": target_tap_to_visible_ms,
        "frame_count": frame_count,
        "interval_histogram": histogram(deltas),
        "gaps_by_threshold": gaps_by_threshold,
        "longest_stall": longest_context,
        "cpu_summary": sorted(cpu_samples, key=lambda row: -row.get("max_cpu_percent", 0)),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="JSON written by tools/theme-swap-jank.py")
    parser.add_argument("--target-tap-to-visible-ms", type=float,
                        default=DEFAULT_TARGET_TAP_TO_VISIBLE_MS)
    parser.add_argument("--max-gap-ms", type=float, default=DEFAULT_MAX_GAP_MS)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        if args.input or args.output:
            parser.error("--self-test cannot read or produce a board report")
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(AnalyzerTests)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    if not args.input:
        parser.error("--input is required (or pass --self-test)")
    try:
        report = json.loads(args.input.read_text())
    except (OSError, json.JSONDecodeError) as error:
        print(f"analyze-theme-swap-jank: {error}", file=sys.stderr)
        return 2
    result = analyze(report, args.target_tap_to_visible_ms, args.max_gap_ms)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0 if result["status"] == "PASS" else 1


# --------------------------------------------------------------------------
# Self-test fixtures and cases
# --------------------------------------------------------------------------

def fixture_smooth_swap() -> dict:
    """One clean crossfade: tap, one commit ~40ms later, steady 16-17ms
    frames for 300ms, nothing over any threshold."""
    events = [{"wall_ms": 1000.0, "source": "rust-shell", "event": "prepare-ack", "raw": ""}]
    t = 1040.0
    for _ in range(18):
        events.append({"wall_ms": t, "source": "rust-shell", "event": "commit", "raw": ""})
        t += 16.7
    return {
        "theme_id": "catppuccin-latte",
        "collected_at": "2026-09-24T00:00:00Z",
        "tap_wall_ms": 1000.0,
        "visible_wall_ms": 1040.0,
        "activation_error": None,
        "events": events,
        "cpu_samples": [{"pid": 1, "label": "rust-shell", "sample_count": 20,
                         "avg_cpu_percent": 12.0, "max_cpu_percent": 40.0}],
    }


def fixture_janky_swap() -> dict:
    """A long stall (Python start-up + synchronous decode) then recovery."""
    events = [
        {"wall_ms": 1000.0, "source": "rust-shell", "event": "prepare-ack", "raw": ""},
        {"wall_ms": 1050.0, "source": "sway", "event": "state", "raw": ""},
        {"wall_ms": 2850.0, "source": "rust-shell", "event": "wallpaper-commit", "raw": ""},
        {"wall_ms": 2900.0, "source": "rust-shell", "event": "commit", "raw": ""},
        {"wall_ms": 2917.0, "source": "rust-shell", "event": "commit", "raw": ""},
    ]
    return {
        "theme_id": "catppuccin",
        "collected_at": "2026-09-24T00:00:00Z",
        "tap_wall_ms": 1000.0,
        "visible_wall_ms": 2850.0,
        "activation_error": None,
        "events": events,
        "cpu_samples": [
            {"pid": 1, "label": "rust-shell", "sample_count": 5,
             "avg_cpu_percent": 5.0, "max_cpu_percent": 20.0},
            {"pid": 2, "label": "helper:python3", "sample_count": 60,
             "avg_cpu_percent": 70.0, "max_cpu_percent": 99.0},
        ],
    }


class AnalyzerTests(unittest.TestCase):
    def test_smooth_swap_passes_with_no_large_gaps(self):
        result = analyze(fixture_smooth_swap(), DEFAULT_TARGET_TAP_TO_VISIBLE_MS, DEFAULT_MAX_GAP_MS)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["tap_to_visible_ms"], 40.0)
        self.assertEqual(result["gaps_by_threshold"]["over_100ms"]["count"], 0)

    def test_janky_swap_fails_on_both_tap_to_visible_and_gap(self):
        result = analyze(fixture_janky_swap(), DEFAULT_TARGET_TAP_TO_VISIBLE_MS, DEFAULT_MAX_GAP_MS)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["tap_to_visible_ms"], 1850.0)
        self.assertTrue(any("tap-to-visible" in failure for failure in result["failures"]))
        self.assertTrue(any("gap(s) exceed" in failure for failure in result["failures"]))
        self.assertIsNotNone(result["longest_stall"])
        self.assertGreater(result["longest_stall"]["gap_ms"], 1000)
        # The stall's surrounding context should include the sway-side event
        # that happened during it, not just the two rust-shell frame events.
        sources = {event["source"] for event in result["longest_stall"]["surrounding_events"]}
        self.assertIn("sway", sources)

    def test_missing_visible_frame_fails_explicitly(self):
        report = fixture_smooth_swap()
        report["visible_wall_ms"] = None
        result = analyze(report, DEFAULT_TARGET_TAP_TO_VISIBLE_MS, DEFAULT_MAX_GAP_MS)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("no visible frame" in failure for failure in result["failures"]))

    def test_activation_error_always_fails_regardless_of_timing(self):
        report = fixture_smooth_swap()
        report["activation_error"] = "commit does not match prepared generation"
        result = analyze(report, DEFAULT_TARGET_TAP_TO_VISIBLE_MS, DEFAULT_MAX_GAP_MS)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("activation failed" in failure for failure in result["failures"]))

    def test_histogram_buckets_sum_to_the_interval_count(self):
        result = analyze(fixture_smooth_swap(), DEFAULT_TARGET_TAP_TO_VISIBLE_MS, DEFAULT_MAX_GAP_MS)
        # 18 real frames plus the synthetic tap->first-frame interval = 18 gaps.
        self.assertEqual(result["frame_count"], 18)
        self.assertEqual(sum(result["interval_histogram"].values()), 18)


if __name__ == "__main__":
    sys.exit(main())
