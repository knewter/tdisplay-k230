#!/usr/bin/env python3
"""Matched-content profiling harness for the Settings theme/background picker.

Subcommands (standard library only, so `capture` runs on the board):

  validate  PLAN                  host/board: check a plan file, touch no device
  preflight --plan PLAN           board: evaluate every comparability gate, no input
  capture   --plan PLAN --output RAW
                                  board, root: bounded injected browsing of both
                                  carousels plus 15-second idle windows. Writes
                                  PRIVATE raw JSON; never activates a theme.
  reduce    RAW --output REPORT   host/board: allowlisted public report, no I/O
                                  beyond the two named files
  compare   A B [--vary FIELD]    host: decide whether two reports are comparable
                                  and, only if so, print per-phase deltas

This is the 13.1 workload from docs/evidence/theme-picker/working-set/capture.py
(preserved unchanged there), restructured around a plan and hard gates. It
never infers disk-cold state and never deletes user caches. Injected input is
not physical-finger proof, and commit gaps are not presentation FPS.

Cost attribution (task 13.2) is opt-in and bounded. A plan may set
`"attribution": true` (per-thread CPU with start-time identity, process RSS and
helper cgroup CPU in every sample) and `"instrumentation"` = off | counters |
trace, which is VERIFIED against the Rust process environment at preflight:

  off       no K230_TRACE_PATH (default)
  counters  K230_TRACE_PATH + K230_TRACE_COUNTERS_ONLY=1 (no event ring)
  trace     K230_TRACE_PATH (event ring + counters)

  reduce RAW --output REPORT [--rust-trace FILE]   adds correlated counters
  overhead OFF ON               host: instrumentation-on/off observer cost, only
                                for otherwise identical, comparable reports
"""
import argparse
import collections
import hashlib
import json
import os
import re
import statistics
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

PLAN_SCHEMA = "k230-theme-picker-profile-plan-v1"
RAW_SCHEMA = "k230-theme-picker-profile-raw-v1"
REPORT_SCHEMA = "k230-theme-picker-profile-report-v1"
COMPARISON_SCHEMA = "k230-theme-picker-profile-comparison-v1"

UNITS = ("shell-ui.service", "shell.service", "theme-helper.service")
DEVICE_NAME = "K230 injected touchscreen"
PANEL = (568, 1232)
PLAYBACK = ("none", "static", "playing", "paused")
PHASE_KINDS = ("baseline", "open", "swipe-theme", "swipe-background", "idle", "back")
IDLE_WINDOW_S = 15
STORE_RE = re.compile(r"/nix/store/[a-z0-9]{32}-[A-Za-z0-9+._?=-]+(?:/[A-Za-z0-9+._?=/~-]+)?")
PHASE_NAME_RE = re.compile(r"[a-z][a-z0-9-]{0,39}")
SHA_RE = re.compile(r"[0-9a-f]{64}")

# Fields that must be identical for two reports to be comparable, except any
# the caller explicitly lets vary (the runtime under test).
INSTRUMENTATION = ("off", "counters", "trace")
# Fixed counter names and gesture phases; pinned to runtime_trace.rs by a test.
COUNTED = ("scene_rebuild", "render_total", "picker_row_repaint", "overlay_draw",
           "thumbnail_request", "thumbnail_completion", "thumbnail_poll", "thumbnail_read_cache",
           "thumbnail_hash", "thumbnail_resolve", "thumbnail_decode",
           "appearance_prepare", "theme_helper_rpc", "theme_request",
           "speculative_admission", "speculative_completion", "overlay_prerender")
GESTURE_PHASES = ("rest", "held", "moving")
THREAD_COMM_RE = re.compile(r"[A-Za-z0-9_.:-]{1,15}")
MAX_THREADS = 64            # per unit per sample; extra threads are counted, not stored
MAX_ATTRIBUTION_SAMPLES = 2000
MAX_TRACE_BYTES = 32 * 1024 * 1024
ATTRIBUTION_UNITS = ("shell-ui.service", "theme-helper.service")

MATCH_FIELDS = (
    "instrumentation", "thread_sampling",
    "kernel_release", "geometry", "background_playback", "catalog",
    "selected_theme_sha256", "generation_sha256", "workload_sha256",
    "openings", "compositor_exe", "helper_exe",
)
VARY_ALLOWED = ("rust_exe", "current_system", "booted_system", "compositor_exe", "helper_exe")
DEFAULT_VARY = ("rust_exe", "current_system", "booted_system")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def store_path(value, what="identity"):
    if not isinstance(value, str) or not STORE_RE.fullmatch(value):
        raise ValueError(f"unexpected store path for {what}")
    return value


# ---------------------------------------------------------------- the plan

def default_workload() -> list[dict]:
    """The historical bounded browsing sequence (1.2 s settle per drag)."""
    steps = [
        {"name": "settings-baseline", "kind": "baseline", "seconds": 2},
        {"name": "first-open", "kind": "open", "seconds": 10, "touch": [480, 130]},
    ]
    for i, (x, x2) in enumerate([(430, 190)] * 3 + [(190, 430)] * 3):
        steps.append({"name": f"theme-swipe-{i}", "kind": "swipe-theme", "seconds": 1.2,
                      "touch": [x, 430, x2, 430]})
    for i, (x, x2) in enumerate([(430, 190)] * 2 + [(190, 430)] * 2):
        steps.append({"name": f"background-swipe-{i}", "kind": "swipe-background",
                      "seconds": 1.2, "touch": [x, 990, x2, 990]})
    steps += [
        {"name": "idle-first", "kind": "idle", "seconds": IDLE_WINDOW_S},
        {"name": "back", "kind": "back", "seconds": 1, "touch": [90, 52]},
        {"name": "warm-open", "kind": "open", "seconds": 5, "touch": [480, 130]},
    ]
    for i, (x, x2) in enumerate([(430, 190)] * 3 + [(190, 430)] * 3):
        steps.append({"name": f"warm-theme-swipe-{i}", "kind": "swipe-theme", "seconds": 1.2,
                      "touch": [x, 430, x2, 430]})
    steps.append({"name": "idle-warm", "kind": "idle", "seconds": IDLE_WINDOW_S})
    return steps


def workload_sha256(workload: list[dict]) -> str:
    return digest(json.dumps(workload, sort_keys=True, separators=(",", ":")))


def validate_plan(plan) -> list[str]:
    """Return a list of plan errors; empty means the plan is well formed."""
    errors: list[str] = []
    if not isinstance(plan, dict):
        return ["plan must be a JSON object"]

    def need(condition, message):
        if not condition:
            errors.append(message)

    need(plan.get("schema") == PLAN_SCHEMA, f"schema must be {PLAN_SCHEMA}")
    need(plan.get("label") in ("baseline", "candidate", "trial"), "label must be baseline, candidate or trial")
    need(re.fullmatch(r"/dev/input/event[0-9]+", str(plan.get("device", ""))) is not None,
         "device must be /dev/input/eventN")
    need(isinstance(plan.get("state_root"), str) and plan["state_root"].startswith("/"),
         "state_root must be an absolute path")
    need(plan.get("settings_ready") is True, "settings_ready must be true (Settings visible)")
    geometry = plan.get("geometry")
    need(isinstance(geometry, dict) and all(isinstance(geometry.get(k), int) and geometry[k] > 0
                                            for k in ("width", "height")),
         "geometry needs positive integer width and height")
    if isinstance(geometry, dict) and (geometry.get("width"), geometry.get("height")) != PANEL:
        errors.append(f"geometry must match the native panel {PANEL[0]}x{PANEL[1]} the injector drives")
    need(plan.get("background_playback") in PLAYBACK, "background_playback must be one of " + "/".join(PLAYBACK))
    need(plan.get("instrumentation", "off") in INSTRUMENTATION,
         "instrumentation must be one of " + "/".join(INSTRUMENTATION))
    need(isinstance(plan.get("attribution", False), bool), "attribution must be a boolean")
    need(plan.get("first_opening") in ("first-observed", "process-cold"),
         "first_opening must be first-observed or process-cold")
    need(isinstance(plan.get("max_process_age_s", 600), (int, float)), "max_process_age_s must be a number")
    rows = plan.get("rows")
    for row in ("themes", "backgrounds"):
        entry = rows.get(row) if isinstance(rows, dict) else None
        if not isinstance(entry, dict):
            errors.append(f"rows.{row} missing")
            continue
        need(isinstance(entry.get("count"), int) and entry["count"] > 0,
             f"rows.{row}.count must be a positive integer (missing row)")
        need(entry.get("resolved") is True, f"rows.{row}.resolved must be true")
        need(entry.get("visually_reviewed") is True, f"rows.{row}.visually_reviewed must be true")
    need(isinstance(plan.get("selected_theme_id"), str) and bool(plan.get("selected_theme_id")),
         "selected_theme_id required (hashed in reports)")
    expect = plan.get("expect")
    if not isinstance(expect, dict):
        errors.append("expect missing")
    else:
        for key in ("rust_exe", "compositor_exe", "helper_exe"):
            try:
                store_path(expect.get(key), "expect." + key)
            except ValueError as error:
                errors.append(str(error))
        need(isinstance(expect.get("generation_sha256"), str) and SHA_RE.fullmatch(expect["generation_sha256"]) is not None,
             "expect.generation_sha256 must be a lowercase sha256")
    errors.extend(validate_workload(plan.get("workload", default_workload())))
    return errors


def validate_workload(workload) -> list[str]:
    errors: list[str] = []
    if not isinstance(workload, list) or not workload:
        return ["workload must be a non-empty list"]
    seen = set()
    for step in workload:
        if not isinstance(step, dict):
            errors.append("workload step must be an object")
            continue
        name = step.get("name")
        if not isinstance(name, str) or not PHASE_NAME_RE.fullmatch(name) or name in seen:
            errors.append(f"bad or duplicate phase name {name!r}")
        seen.add(name)
        kind = step.get("kind")
        if kind not in PHASE_KINDS:
            errors.append(f"{name}: unknown kind")
        seconds = step.get("seconds")
        if not isinstance(seconds, (int, float)) or not 0 < seconds <= 60:
            errors.append(f"{name}: seconds must be in (0, 60]")
        if kind == "idle" and seconds != IDLE_WINDOW_S:
            errors.append(f"{name}: idle windows are {IDLE_WINDOW_S} seconds")
        touch = step.get("touch")
        if kind in ("idle", "baseline") and touch:
            errors.append(f"{name}: idle/baseline phases cannot inject touch")
        if touch is not None:
            if len(touch) not in (2, 4) or not all(isinstance(v, int) for v in touch):
                errors.append(f"{name}: touch needs 2 or 4 integers")
            else:
                points = [(touch[i], touch[i + 1]) for i in range(0, len(touch), 2)]
                if any(not (0 <= x < PANEL[0] and 0 <= y < PANEL[1]) for x, y in points):
                    errors.append(f"{name}: touch outside native panel")
        elif kind in ("open", "swipe-theme", "swipe-background", "back"):
            errors.append(f"{name}: needs touch")
    kinds = [s.get("kind") for s in workload if isinstance(s, dict)]
    if "swipe-theme" not in kinds:
        errors.append("workload needs at least one theme swipe")
    return errors


# ------------------------------------------------------- comparability gates

def classify_opening(requested: str, *, prior_touch_events, process_age_s, max_age_s) -> str:
    """Opening history of the first opening. Never claims disk-cold.

    `process-cold` is granted only when the process is young and the journal
    shows it never saw touch input before this capture; otherwise it is
    refused (ValueError) rather than silently downgraded.
    """
    if requested == "first-observed":
        return "first-observed"
    if requested != "process-cold":
        raise ValueError("unknown opening request")
    if prior_touch_events is None or process_age_s is None:
        raise ValueError("process-cold unverifiable: no journal or process age")
    if prior_touch_events != 0:
        raise ValueError("process-cold refused: process already saw touch input")
    if process_age_s > max_age_s:
        raise ValueError("process-cold refused: process older than allowed")
    return "process-cold"


def precondition_failures(plan: dict, observed: dict) -> list[str]:
    """Compare declared plan expectations with observations from the board."""
    failures: list[str] = []
    expect = plan["expect"]
    rows = plan["rows"]
    for row, key in (("themes", "theme_count"), ("backgrounds", "background_count")):
        seen = observed.get(key)
        if not seen:
            failures.append(f"{row} row missing or empty in observed catalog")
        elif seen != rows[row]["count"]:
            failures.append(f"{row} count {seen} != planned {rows[row]['count']}")
    exes = observed.get("exes", {})
    for unit, key in (("shell-ui.service", "rust_exe"), ("shell.service", "compositor_exe"),
                      ("theme-helper.service", "helper_exe")):
        if exes.get(unit) != expect[key]:
            failures.append(f"{unit} executable differs from plan")
    if observed.get("generation_sha256") != expect["generation_sha256"]:
        failures.append("active generation differs from plan")
    if observed.get("instrumentation", "off") != plan.get("instrumentation", "off"):
        failures.append("Rust instrumentation mode differs from plan")
    if observed.get("selected_theme_sha256") not in (None, digest(plan["selected_theme_id"])):
        failures.append("selected theme differs from plan")
    return failures


def check_sample(identities: dict, sample: dict, generation_sha256: str) -> None:
    """Abort on PID reuse (start_ticks change), a vanished unit, or a changed generation."""
    for unit, identity in identities.items():
        values = sample["units"].get(unit)
        if values is None:
            raise RuntimeError("unit missing from sample: " + unit)
        if values["start_ticks"] != identity["start_ticks"]:
            raise RuntimeError("PID identity changed: " + unit)
    if sample["generation_sha256"] != generation_sha256:
        raise RuntimeError("active generation changed; stop browsing")


# --------------------------------------------------------------- the reducer

EVENT_TOUCH = re.compile(r"touch-(down|move) -?\d+ -?\d+(?:\.\d+)? -?\d+(?:\.\d+)?")
EVENT_CMD = re.compile(r"theme-command (list|preview|activate) (?:[a-f0-9]+|-) path=(socket|fallback) ms=(\d+)")


def parse_event(message):
    """Return (rust_ms, kind, command) for an allowlisted shell log line, else None."""
    match = re.fullmatch(r"rust-shell (\d+)ms (.*)", message if isinstance(message, str) else "")
    if not match:
        return None
    rust_ms, text = int(match[1]), match[2]
    command = EVENT_CMD.fullmatch(text)
    if command:
        return rust_ms, "theme-command", {"action": command[1], "transport": command[2],
                                          "duration_ms": int(command[3])}
    if text in ("commit", "frame-done", "wallpaper-commit"):
        return rust_ms, text, None
    touch = EVENT_TOUCH.fullmatch(text)
    if touch:
        return rust_ms, "touch-" + touch[1], None
    if re.fullmatch(r"touch-up -?\d+", text):
        return rust_ms, "touch-up", None
    if re.fullmatch(r"optimistic-apply prerendered generation=[a-f0-9]+", text):
        return rust_ms, "prerender-completed", None
    return None


def swipe_gaps(commit_ms: list[int]) -> list[int]:
    """Gaps between consecutive `commit` events of ONE swipe phase. Callback
    (`frame-done`) and `wallpaper-commit` events are never mixed in."""
    ordered = sorted(commit_ms)
    return [b - a for a, b in zip(ordered, ordered[1:])]


def _p95(values):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]


def reduce_raw(raw: dict, rust_trace: dict | None = None) -> dict:
    """Allowlisted public report from a private capture. Raises on malformed input.
    `rust_trace` is the optional Rust recorder report (task 13.2)."""
    if raw.get("schema") != RAW_SCHEMA:
        raise ValueError("not a raw picker profile capture")
    identities = raw["identities"]
    ui_pid = int(identities["shell-ui.service"]["pid"])
    failures = list(raw.get("precondition_failures", [])) + attribution_failures(raw)
    parsed, commands = [], []
    foreign, previous_rust_ms = 0, -1
    for event in raw.get("events", []):
        ui = event.get("unit") == "shell-ui.service"
        if ui and event.get("pid") not in (None, ui_pid):
            foreign += 1  # PID reuse or a restarted process: never mixed into the run
            continue
        got = parse_event(event.get("message"))
        if got is None or not event.get("monotonic_us"):
            continue
        rust_ms, kind, command = got
        if ui:
            if rust_ms < previous_rust_ms:
                failures.append("Rust elapsed clock went backwards (process restart)")
            previous_rust_ms = rust_ms
        if command:
            commands.append(command)
        else:
            parsed.append({"rust_ms": rust_ms, "monotonic_s": int(event["monotonic_us"]) / 1e6, "kind": kind})
    if foreign:
        failures.append(f"{foreign} shell-ui events from a different PID")
    if any(c["action"] == "activate" for c in commands):
        failures.append("theme activation observed; this workload must not activate")
    if not raw.get("generation_unchanged", False):
        failures.append("active generation changed during capture")
    if raw.get("status") != "CAPTURED_REQUIRES_REVIEW":
        failures.append("capture did not complete")

    held, pre, held_pre = False, 0, 0
    for event in sorted(parsed, key=lambda e: e["rust_ms"]):
        if event["kind"] == "touch-down":
            held = True
        elif event["kind"] == "touch-up":
            held = False
        elif event["kind"] == "prerender-completed":
            pre += 1
            held_pre += held

    phases = []
    for phase in raw["phases"]:
        if "end_monotonic_s" not in phase:
            continue
        name, kind = phase["name"], phase["kind"]
        if not PHASE_NAME_RE.fullmatch(name) or kind not in PHASE_KINDS:
            raise ValueError("unexpected phase")
        a, b = phase["start_monotonic_s"], phase["end_monotonic_s"]
        rows = [s for s in raw["samples"] if a <= s["monotonic_s"] <= b]
        out = {"name": name, "kind": kind, "opening": phase.get("opening"),
               "duration_s": round(b - a, 4), "sample_count": len(rows)}
        if "injection_end_monotonic_s" in phase:
            out["injection_duration_ms"] = round(1000 * (phase["injection_end_monotonic_s"] - a), 3)
        if len(rows) > 1:
            first, last = rows[0], rows[-1]
            dt = last["monotonic_s"] - first["monotonic_s"]
            out["sampled_s"] = round(dt, 4)
            out["units"] = {}
            for unit in UNITS:
                x, y = first["units"][unit], last["units"][unit]
                out["units"][unit] = {
                    "process_cpu_percent": round(100 * (y["ticks"] - x["ticks"]) / raw["clock_ticks_per_second"] / dt, 3),
                    "cgroup_cpu_percent": round(100 * (y["cgroup_cpu"]["usage_usec"] - x["cgroup_cpu"]["usage_usec"]) / 1e6 / dt, 3),
                    "rss_first_bytes": x["rss_bytes"], "rss_last_bytes": y["rss_bytes"],
                    "rss_peak_bytes": max(s["units"][unit]["rss_bytes"] for s in rows)}
        attribution = reduce_attribution(raw, phase, rows)
        if attribution:
            out["attribution"] = attribution
        events = [e for e in parsed if a <= e["monotonic_s"] <= b]
        out["events"] = dict(collections.Counter(e["kind"] for e in events))
        commits = [e["rust_ms"] for e in events if e["kind"] == "commit"]
        if kind in ("swipe-theme", "swipe-background"):
            gaps = swipe_gaps(commits)
            out["commit_gaps_ms"] = gaps
            out["commit_gap_median_ms"] = statistics.median(gaps) if gaps else None
            out["commit_gap_p95_ms"] = _p95(gaps) if gaps else None
            out["commit_gap_max_ms"] = max(gaps) if gaps else None
            if not gaps:
                failures.append(f"{name}: no commit gaps observed")
        elif kind == "idle":
            out["idle_commit_count"] = len(commits)  # a count, never a frame gap
        phases.append(out)

    for kind in ("swipe-theme", "swipe-background"):
        if not any(p["kind"] == kind for p in phases):
            failures.append(f"no completed {kind} phase")
    obs = raw["observed"]
    exes = obs["exes"]
    rust_counters = None
    if rust_trace is not None:
        rust_counters = reduce_rust_trace(rust_trace, ui_pid=ui_pid, phases=raw["phases"],
                                          start_s=raw["start_monotonic_s"], end_s=raw["end_monotonic_s"])
        failures.extend("rust trace: " + f for f in rust_counters["failures"])
        if raw.get("instrumentation", "off") == "off":
            failures.append("rust trace supplied for a capture with instrumentation off")
    elif raw.get("instrumentation", "off") != "off":
        failures.append("instrumentation was on but no Rust trace was supplied")
    report = {
        "schema": REPORT_SCHEMA,
        "label": raw["label"] if raw["label"] in ("baseline", "candidate", "trial") else "trial",
        "comparable_inputs_valid": not failures,
        "failures": sorted(set(failures)),
        "provenance": "injected verified virtual touchscreen; no physical-finger or presentation-FPS claim",
        "openings": [p["opening"] for p in phases if p["kind"] == "open"],
        "opening_notes": "process-cold is journal/age verified only; disk-cold is never inferred and user caches are not cleared",
        "catalog": {"theme_count": obs["theme_count"], "background_count": obs["background_count"],
                    "rows_visually_reviewed": bool(raw["plan_rows_reviewed"])},
        "geometry": raw["geometry"],
        "background_playback": raw["background_playback"],
        "selected_theme_sha256": digest(raw["selected_theme_id"]),
        "generation_sha256": obs["generation_sha256"],
        "generation_unchanged": bool(raw.get("generation_unchanged")),
        "generation_samples": len(raw["samples"]),
        "workload_sha256": workload_sha256(raw["workload"]),
        "kernel_release": raw["kernel_release"],
        "booted_system": store_path(raw["booted_system"], "booted_system"),
        "current_system": store_path(raw["current_system"], "current_system"),
        "rust_exe": store_path(exes["shell-ui.service"], "rust_exe"),
        "compositor_exe": store_path(exes["shell.service"], "compositor_exe"),
        "helper_exe": store_path(exes["theme-helper.service"], "helper_exe"),
        "runtime": {unit: {"pid": int(identities[unit]["pid"]),
                           "start_ticks": int(identities[unit]["start_ticks"])} for unit in UNITS},
        "duration_s": round(raw["end_monotonic_s"] - raw["start_monotonic_s"], 4),
        "event_counts": dict(collections.Counter(e["kind"] for e in parsed)),
        "speculative_prerender_completions": pre,
        "speculative_completions_while_touch_held": held_pre,
        "theme_commands": commands,
        "phases": phases,
        "limits": [
            "Commit gaps use Rust elapsed timestamps of `commit` events inside one swipe phase; "
            "idle intervals, frame callbacks and wallpaper commits are never mixed into them.",
            "Swipe windows include the settling period after injection.",
            "CPU samples are about 0.5 s apart; short phases have partial coverage.",
            "Span/counter attribution exists only where `rust_counters` is present; no native media during this pass.",
        ],
    }
    report["instrumentation"] = raw.get("instrumentation", "off")
    report["thread_sampling"] = bool(raw.get("thread_sampling", False))
    if rust_counters is not None:
        report["rust_counters"] = rust_counters
    report["comparable_inputs_valid"] = not failures
    report["failures"] = sorted(set(failures))
    return report


# ------------------------------------------------------------- comparison

def compare_reports(a: dict, b: dict, vary: tuple = DEFAULT_VARY) -> dict:
    """Gate, then compare. Deltas are emitted only when every gate passes."""
    unknown = [v for v in vary if v not in VARY_ALLOWED]
    if unknown:
        raise ValueError("cannot vary: " + ", ".join(unknown))
    mismatches = []
    for report, tag in ((a, "A"), (b, "B")):
        if report.get("schema") != REPORT_SCHEMA:
            mismatches.append(f"{tag}: not a profile report")
        elif not report.get("comparable_inputs_valid"):
            mismatches.append(f"{tag}: report has failed gates: " + "; ".join(report.get("failures", [])))
    if not mismatches:
        for field in MATCH_FIELDS:
            if field not in vary and a.get(field) != b.get(field):
                mismatches.append(f"{field} differs")
        for tag, report in (("A", a), ("B", b)):
            catalog = report["catalog"]
            if not catalog["theme_count"] or not catalog["background_count"]:
                mismatches.append(f"{tag}: missing row")
            if not catalog["rows_visually_reviewed"]:
                mismatches.append(f"{tag}: rows not visually reviewed")
        if [p["name"] for p in a["phases"]] != [p["name"] for p in b["phases"]]:
            mismatches.append("completed phase lists differ")
    result = {"schema": COMPARISON_SCHEMA, "comparable": not mismatches,
              "mismatches": mismatches, "varied": list(vary), "phases": []}
    if mismatches:
        return result
    for left, right in zip(a["phases"], b["phases"]):
        entry = {"name": left["name"], "kind": left["kind"], "opening": left.get("opening")}
        if left["kind"].startswith("swipe"):
            for key in ("commit_gap_median_ms", "commit_gap_p95_ms", "commit_gap_max_ms"):
                entry[key] = {"a": left[key], "b": right[key]}
        elif left["kind"] == "idle":
            entry["idle_commit_count"] = {"a": left["idle_commit_count"], "b": right["idle_commit_count"]}
        if "units" in left and "units" in right:
            ua, ub = left["units"]["shell-ui.service"], right["units"]["shell-ui.service"]
            entry["rust_cpu_percent"] = {"a": ua["process_cpu_percent"], "b": ub["process_cpu_percent"]}
            entry["rust_rss_last_bytes"] = {"a": ua["rss_last_bytes"], "b": ub["rss_last_bytes"]}
        result["phases"].append(entry)
    return result


# ------------------------------------------- cost attribution (task 13.2)

def instrumentation_from_environ(environ: bytes) -> str:
    """Classify the Rust process's recorder mode from /proc/PID/environ bytes."""
    names = {}
    for item in environ.split(b"\0"):
        key, sep, value = item.partition(b"=")
        if sep:
            names[key] = value
    if b"K230_TRACE_PATH" not in names:
        return "off"
    return "counters" if names.get(b"K230_TRACE_COUNTERS_ONLY") == b"1" else "trace"


def parse_task_stat(text: str) -> dict:
    """One /proc/PID/task/TID/stat line -> comm, state, CPU ticks, start ticks.
    `comm` may contain spaces and parentheses, so split at the LAST ')'."""
    head, sep, tail = text.rpartition(")")
    comm = head.partition("(")[2]
    fields = tail.split()
    if not sep or len(fields) < 20:
        raise ValueError("malformed task stat")
    return {"comm": comm if THREAD_COMM_RE.fullmatch(comm) else "other", "state": fields[0],
            "ticks": int(fields[11]) + int(fields[12]), "start_ticks": int(fields[19])}


def read_threads(pid: int, limit: int = MAX_THREADS):
    """Bounded per-thread sample: {tid: stat}, number of threads not stored."""
    threads, dropped = {}, 0
    for entry in sorted(os.listdir(f"/proc/{pid}/task"), key=int):
        try:
            stat = parse_task_stat((Path(f"/proc/{pid}/task/{entry}/stat")).read_text())
        except (OSError, ValueError):
            continue  # exited between listing and reading
        if len(threads) < limit:
            threads[entry] = stat
        else:
            dropped += 1
    return threads, dropped


def _delta_series(rows: list, ticks_per_second: int):
    """Pairwise per-thread CPU deltas across consecutive samples of ONE unit.

    Same tid + same start_ticks: delta. Smaller counter: discontinuity, delta
    excluded. Same tid with a new start_ticks: tid reuse, a new thread (its CPU
    since start is attributed, the old one is counted as exited). Thread seen
    first time: new (CPU since start attributed). Vanished: counted as exited;
    its last interval is unobservable and is not guessed."""
    cpu_s, notes = collections.defaultdict(float), collections.Counter()
    for prev, cur in zip(rows, rows[1:]):
        for tid, now in cur["threads"].items():
            before = prev["threads"].get(tid)
            if before is not None and before["start_ticks"] == now["start_ticks"]:
                if now["ticks"] < before["ticks"]:
                    notes["counter_discontinuities"] += 1
                    continue
                cpu_s[now["comm"]] += (now["ticks"] - before["ticks"]) / ticks_per_second
            else:
                if before is not None:
                    notes["identity_changes"] += 1
                notes["threads_started"] += 1
                cpu_s[now["comm"]] += now["ticks"] / ticks_per_second
        notes["threads_exited"] += sum(
            1 for tid in prev["threads"] if tid not in cur["threads"])
        notes["threads_unstored"] += cur.get("threads_dropped", 0)
    return cpu_s, notes


def reduce_attribution(raw: dict, phase: dict, rows: list) -> dict | None:
    """Per-phase thread/RSS/cgroup attribution from raw samples, or None when the
    capture did not sample threads. CPU time is thread CPU seconds; `wall_s` is
    the sampled wall interval, so a percentage is CPU/wall and can exceed 100."""
    if not raw.get("thread_sampling"):
        return None
    ticks = raw["clock_ticks_per_second"]
    out = {}
    for unit in ATTRIBUTION_UNITS:
        series = [{"threads": r["units"][unit].get("threads", {}),
                   "threads_dropped": r["units"][unit].get("threads_dropped", 0),
                   "pid": r["units"][unit].get("threads_pid"),
                   "monotonic_s": r["monotonic_s"], "u": r["units"][unit]} for r in rows]
        if len(series) < 2:
            continue
        wall = series[-1]["monotonic_s"] - series[0]["monotonic_s"]
        cpu_s, notes = _delta_series(series, ticks)
        cg = [r["u"]["cgroup_cpu"]["usage_usec"] for r in series]
        cg_notes = sum(1 for a, b in zip(cg, cg[1:]) if b < a)
        cg_s = sum(b - a for a, b in zip(cg, cg[1:]) if b >= a) / 1e6
        out[unit] = {
            "wall_s": round(wall, 4),
            "threads_cpu": {comm: {"cpu_s": round(v, 4), "cpu_percent": round(100 * v / wall, 3)}
                            for comm, v in sorted(cpu_s.items())},
            "threads_cpu_total_s": round(sum(cpu_s.values()), 4),
            "cgroup_cpu_s": round(cg_s, 4), "cgroup_cpu_percent": round(100 * cg_s / wall, 3),
            "cgroup_discontinuities": cg_notes,
            "rss_peak_bytes": max(r["u"]["rss_bytes"] for r in series),
            "notes": dict(notes)}
    return out or None


def attribution_failures(raw: dict) -> list[str]:
    """Run-level failures: sampling gaps, PID discontinuity, unbounded sampling."""
    if not raw.get("thread_sampling"):
        return []
    failures = []
    if len(raw["samples"]) > MAX_ATTRIBUTION_SAMPLES:
        failures.append("thread sampling exceeded its sample bound")
    for unit in ATTRIBUTION_UNITS:
        pid = int(raw["identities"][unit]["pid"])
        for sample in raw["samples"]:
            values = sample["units"].get(unit, {})
            if "threads" not in values:
                failures.append(f"{unit}: sample without thread data")
                break
            if values.get("threads_pid") not in (None, pid):
                failures.append(f"{unit}: thread PID discontinuity")
                break
    return failures


def _overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def reduce_rust_trace(trace: dict, *, ui_pid: int, phases: list, start_s: float, end_s: float) -> dict:
    """Correlate the Rust recorder's counters with harness and gesture phases.

    Counters (always exact, however many events overflowed) are totals per
    gesture phase. Per-harness-phase figures need the event ring and are only
    produced when it is complete. Span times are inclusive of nested spans, so
    kinds must not be summed. Wall time and thread CPU time are separate."""
    failures = []
    if not isinstance(trace, dict) or trace.get("schema") != 1 or trace.get("clock") != "CLOCK_MONOTONIC":
        return {"valid": False, "failures": ["not a monotonic Rust trace report"]}
    if trace.get("pid") != ui_pid:
        failures.append("Rust trace is from a different PID")
    counters_only = bool(trace.get("counters_only", False))
    by_gesture = {}
    for c in trace.get("counters", []):
        if (c.get("kind") not in COUNTED or c.get("phase") not in GESTURE_PHASES
                or not all(isinstance(c.get(k), int) and c[k] >= 0 for k in ("count", "wall_us", "cpu_us", "max_wall_us"))
                or (c["count"] == 0 and (c["wall_us"] or c["cpu_us"]))):
            failures.append("malformed or unexpected counter")
            continue
        by_gesture.setdefault(c["phase"], {})[c["kind"]] = {
            "count": c["count"], "wall_ms": round(c["wall_us"] / 1000, 3),
            "cpu_ms": round(c["cpu_us"] / 1000, 3), "max_wall_ms": round(c["max_wall_us"] / 1000, 3)}
    log = trace.get("phase_log", [])
    times = [e.get("t_us") for e in log]
    if (any(not isinstance(t, int) for t in times) or times != sorted(times)
            or any(e.get("phase") not in GESTURE_PHASES for e in log)):
        failures.append("phase log malformed or clock went backwards")
        log = []
    if log and not (start_s - 1 <= log[0]["t_us"] / 1e6 and log[-1]["t_us"] / 1e6 <= end_s + 1):
        failures.append("Rust trace clock does not overlap the capture window")
    # gesture phase intervals: rest until the first logged change
    intervals, prev_t, prev_phase = [], start_s, "rest"
    for e in log:
        t = e["t_us"] / 1e6
        intervals.append((prev_t, t, prev_phase))
        prev_t, prev_phase = t, e["phase"]
    intervals.append((prev_t, end_s, prev_phase))
    out_phases = []
    events = trace.get("events", [])
    complete = (not counters_only) and trace.get("dropped", 0) == 0 and bool(events)
    for phase in phases:
        if "end_monotonic_s" not in phase:
            continue
        a, b = phase["start_monotonic_s"], phase["end_monotonic_s"]
        entry = {"name": phase["name"], "kind": phase["kind"],
                 "gesture_phase_s": {g: round(sum(_overlap(a, b, i0, i1) for i0, i1, g2 in intervals if g2 == g), 4)
                                     for g in GESTURE_PHASES}}
        if complete:
            kinds = {}
            for e in events:
                kind = e.get("kind")
                if kind not in COUNTED:
                    continue
                s0, s1 = e["start_us"] / 1e6, e["end_us"] / 1e6
                row = kinds.setdefault(kind, {"count": 0, "wall_ms": 0.0, "cpu_ms": 0.0})
                if a <= s0 < b:
                    row["count"] += 1
                if s1 > s0:
                    share = _overlap(a, b, s0, s1) / (s1 - s0)  # span straddling a boundary is split by wall overlap
                    row["wall_ms"] += share * (s1 - s0) * 1000
                    row["cpu_ms"] += share * e["cpu_us"] / 1000
            entry["counters"] = {k: {"count": v["count"], "wall_ms": round(v["wall_ms"], 3), "cpu_ms": round(v["cpu_ms"], 3)}
                                 for k, v in sorted(kinds.items()) if v["count"] or v["wall_ms"]}
        out_phases.append(entry)
    return {"valid": not failures, "failures": sorted(set(failures)), "counters_only": counters_only,
            "events_complete": complete, "events_dropped": trace.get("dropped", 0),
            "phase_log_dropped": trace.get("phase_log_dropped", 0),
            "by_gesture_phase": by_gesture, "phases": out_phases,
            "limits": ["Span wall/CPU are inclusive of nested spans; do not sum kinds.",
                       "Thread CPU is per recording thread; helper subprocess CPU is in the cgroup figures.",
                       "Coasting and settling share the `moving` gesture phase.",
                       "Per-harness-phase counters need a complete event ring (trace mode, no drops)."]}


def overhead_pair(off: dict, on: dict) -> dict:
    """Observer cost of the recorder: OFF versus ON reports of otherwise identical
    runs. Refuses to compare anything else; deltas are measurements of one pair,
    not statistics, and detailed timings should not be interpreted until the
    overhead is known to be small."""
    mismatches = []
    for report, tag in ((off, "OFF"), (on, "ON")):
        if report.get("schema") != REPORT_SCHEMA:
            mismatches.append(f"{tag}: not a profile report")
        elif not report.get("comparable_inputs_valid"):
            mismatches.append(f"{tag}: report has failed gates")
    if not mismatches:
        if off.get("instrumentation") != "off":
            mismatches.append("first report must have instrumentation off")
        if on.get("instrumentation") not in ("counters", "trace"):
            mismatches.append("second report must have instrumentation counters or trace")
        for field in MATCH_FIELDS:
            if field != "instrumentation" and off.get(field) != on.get(field):
                mismatches.append(f"{field} differs")
        for field in ("rust_exe", "current_system", "booted_system"):
            if off.get(field) != on.get(field):
                mismatches.append(f"{field} differs (overhead needs the same build)")
        if [p["name"] for p in off["phases"]] != [p["name"] for p in on["phases"]]:
            mismatches.append("completed phase lists differ")
    result = {"schema": COMPARISON_SCHEMA, "kind": "instrumentation-overhead", "comparable": not mismatches,
              "mismatches": sorted(set(mismatches)), "phases": []}
    if mismatches:
        return result
    result["instrumentation"] = on["instrumentation"]
    for left, right in zip(off["phases"], on["phases"]):
        entry = {"name": left["name"], "kind": left["kind"]}
        if "units" in left and "units" in right:
            for unit in ATTRIBUTION_UNITS:
                a, b = left["units"][unit], right["units"][unit]
                entry[unit] = {"process_cpu_percent": {"off": a["process_cpu_percent"], "on": b["process_cpu_percent"],
                                                       "delta": round(b["process_cpu_percent"] - a["process_cpu_percent"], 3)},
                               "cgroup_cpu_percent": {"off": a["cgroup_cpu_percent"], "on": b["cgroup_cpu_percent"],
                                                      "delta": round(b["cgroup_cpu_percent"] - a["cgroup_cpu_percent"], 3)},
                               "rss_peak_bytes": {"off": a["rss_peak_bytes"], "on": b["rss_peak_bytes"],
                                                  "delta": b["rss_peak_bytes"] - a["rss_peak_bytes"]}}
        if left["kind"].startswith("swipe") and left.get("commit_gap_p95_ms") is not None and right.get("commit_gap_p95_ms") is not None:
            entry["commit_gap_p95_ms"] = {"off": left["commit_gap_p95_ms"], "on": right["commit_gap_p95_ms"],
                                          "delta": right["commit_gap_p95_ms"] - left["commit_gap_p95_ms"]}
        result["phases"].append(entry)
    result["limits"] = ["One OFF/ON pair is a measurement, not a distribution; repeat before trusting small deltas.",
                        "Both runs must use the same injected workload and no native screencopy."]
    return result


# ------------------------------------------------------------ board capture

def verify_device(device: str) -> None:
    if not re.fullmatch(r"/dev/input/event[0-9]+", device):
        raise ValueError("expected an input event device")
    path = Path("/sys/class/input") / Path(device).name / "device/name"
    if path.read_text().strip() != DEVICE_NAME:
        raise RuntimeError("fixture name mismatch")
    if not str(path.resolve()).startswith("/sys/devices/virtual/input/"):
        raise RuntimeError("refusing a physical input device")


def native_touch(device, x, y, x2=None, y2=None):
    """Write Linux input_event packets to the verified virtual touchscreen
    (the existing single-process injector; kernel timestamps authoritative).
    Software input, not physical touch."""
    verify_device(device)
    points = [(x, y)] if x2 is None else [(x, y), (x2, y2)]
    if any(not (0 <= px < PANEL[0] and 0 <= py < PANEL[1]) for px, py in points):
        raise ValueError("touch coordinates outside native panel")
    event = struct.Struct("@llHHi")

    def position(px, py):
        dx = px * 1024 // 568
        dy = py * 2400 // 1232
        return [(3, 53, dx), (3, 54, dy), (3, 0, dx), (3, 1, dy)]

    fd = os.open(device, os.O_WRONLY | os.O_CLOEXEC)

    def frame(events):
        packet = b"".join(event.pack(0, 0, *values) for values in [*events, (0, 0, 0)])
        if os.write(fd, packet) != len(packet):
            raise OSError("short input-event write")

    try:
        frame([(3, 47, 0), (3, 57, 7), (3, 48, 3), (1, 330, 1), *position(x, y)])
        start = time.monotonic()
        if x2 is None:
            time.sleep(0.08)
        else:
            for i in range(1, 21):
                time.sleep(max(0, start + i * 0.01 - time.monotonic()))
                frame(position(x + (x2 - x) * i // 20, y + (y2 - y) * i // 20))
    finally:
        try:
            frame([(3, 57, -1), (1, 330, 0)])
        finally:
            os.close(fd)


def prop(unit: str, field: str) -> str:
    return subprocess.check_output(["systemctl", "show", unit, "-p", field, "--value"],
                                   text=True, timeout=5).strip()


def proc_stat(pid: int) -> dict:
    s = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
    return {"ticks": int(s[11]) + int(s[12]), "start_ticks": int(s[19]),
            "rss_bytes": int(s[21]) * os.sysconf("SC_PAGE_SIZE")}


def unit_identities() -> dict:
    out = {}
    for unit in UNITS:
        pid = int(prop(unit, "MainPID"))
        if pid <= 0:
            raise RuntimeError("unit not running: " + unit)
        out[unit] = {"pid": pid, "exe": os.readlink(f"/proc/{pid}/exe"),
                     "cgroup": prop(unit, "ControlGroup"), "start_ticks": proc_stat(pid)["start_ticks"]}
    return out


def read_generation(state_root: Path) -> str:
    return str((state_root / "active").resolve(strict=True))


def observe(plan: dict, identities: dict) -> dict:
    """Facts read from the board; the plan is only compared against these."""
    generation = read_generation(Path(plan["state_root"]))
    observed = {"exes": {u: i["exe"] for u, i in identities.items()},
                "generation_sha256": digest(generation)}
    try:
        observed["instrumentation"] = instrumentation_from_environ(
            Path(f"/proc/{identities['shell-ui.service']['pid']}/environ").read_bytes())
    except OSError:
        observed["instrumentation"] = None  # unreadable: the precondition gate refuses it
    try:
        report = json.loads((Path(generation) / "report.json").read_text())
        observed["background_count"] = len(report["backgrounds"])
    except (OSError, ValueError, KeyError):
        observed["background_count"] = None
    try:
        listing = subprocess.run([plan.get("theme_command", "/run/current-system/sw/bin/k230-theme"), "list"],
                                 capture_output=True, text=True, timeout=30, check=True).stdout
        themes = json.loads(listing)["themes"]
        observed["theme_count"] = len(themes)
        active = [t for t in themes if t.get("active")]
        observed["selected_theme_sha256"] = digest(active[0]["id"]) if len(active) == 1 and "id" in active[0] else None
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        observed["theme_count"] = None
        observed["selected_theme_sha256"] = None
    return observed


def journal_prior_touches(pid: int):
    """Count touch-down lines this exact PID logged before capture, or None."""
    try:
        raw = subprocess.run(["journalctl", "-o", "json", "-u", "shell-ui.service", f"_PID={pid}", "--no-pager"],
                             capture_output=True, text=True, timeout=20, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return sum(1 for line in raw.splitlines() if " touch-down " in line)


def load_plan(path: Path) -> dict:
    plan = json.loads(path.read_text())
    errors = validate_plan(plan)
    if errors:
        raise ValueError("invalid plan: " + "; ".join(errors))
    plan.setdefault("workload", default_workload())
    return plan


def preflight(plan: dict):
    verify_device(plan["device"])
    identities = unit_identities()
    observed = observe(plan, identities)
    failures = precondition_failures(plan, observed)
    ui = identities["shell-ui.service"]
    age = time.monotonic() - ui["start_ticks"] / os.sysconf("SC_CLK_TCK")
    prior = journal_prior_touches(ui["pid"]) if plan["first_opening"] == "process-cold" else 0
    try:
        opening = classify_opening(plan["first_opening"], prior_touch_events=prior, process_age_s=age,
                                   max_age_s=plan.get("max_process_age_s", 600))
    except ValueError as error:
        failures.append(str(error))
        opening = "first-observed"
    return identities, observed, failures, opening


def capture(plan: dict, output: Path) -> int:
    if os.geteuid() != 0:
        raise RuntimeError("requires root on the reserved board")
    if output.exists():
        raise RuntimeError("refusing to overwrite evidence")
    identities, observed, failures, first_opening = preflight(plan)
    state_root = Path(plan["state_root"])
    generation = read_generation(state_root)
    gen_sha = observed["generation_sha256"]
    raw = {"schema": RAW_SCHEMA, "label": plan["label"], "workload": plan["workload"],
           "geometry": plan["geometry"], "background_playback": plan["background_playback"],
           "selected_theme_id": plan["selected_theme_id"],
           "instrumentation": plan.get("instrumentation", "off"),
           "thread_sampling": bool(plan.get("attribution", False)),
           "plan_rows_reviewed": all(r["visually_reviewed"] and r["resolved"] for r in plan["rows"].values()),
           "clock_ticks_per_second": os.sysconf("SC_CLK_TCK"),
           "booted_system": str(Path("/run/booted-system").resolve()),
           "current_system": str(Path("/run/current-system").resolve()),
           "kernel_release": os.uname().release, "identities": identities, "observed": observed,
           "precondition_failures": failures, "phases": [], "samples": [], "errors": [], "events": [],
           "provenance": "injected-input-event; not physical finger proof"}
    if failures:
        now = time.monotonic()
        raw.update(status="PRECONDITION_FAILED", generation_unchanged=True, start_monotonic_s=now, end_monotonic_s=now)
        output.write_text(json.dumps(raw, indent=2) + "\n")
        print("PRECONDITION_FAILED", output, file=sys.stderr)
        for failure in failures:
            print("  -", failure, file=sys.stderr)
        return 1
    stop = threading.Event()
    start, epoch = time.monotonic(), time.time()

    def sample():
        row = {"monotonic_s": time.monotonic(), "generation_sha256": digest(read_generation(state_root)), "units": {}}
        for unit, identity in identities.items():
            values = proc_stat(identity["pid"])
            cpu = Path("/sys/fs/cgroup" + identity["cgroup"]) / "cpu.stat"
            values["cgroup_cpu"] = {k: int(v) for k, v in (line.split() for line in cpu.read_text().splitlines())}
            if plan.get("attribution") and unit in ATTRIBUTION_UNITS:
                values["threads_pid"] = identity["pid"]
                values["threads"], values["threads_dropped"] = read_threads(identity["pid"])
            row["units"][unit] = values
        if len(raw["samples"]) >= MAX_ATTRIBUTION_SAMPLES:
            raise RuntimeError("sample bound reached; workload too long for bounded telemetry")
        raw["samples"].append(row)
        check_sample(identities, row, gen_sha)

    def monitor():
        while not stop.is_set():
            try:
                sample()
            except Exception as error:
                raw["errors"].append(str(error))
                stop.set()
                return
            stop.wait(0.5)

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    try:
        opened = 0
        for step in plan["workload"]:
            if stop.is_set():
                raise RuntimeError("monitor failed: " + str(raw["errors"]))
            item = {"name": step["name"], "kind": step["kind"], "start_monotonic_s": time.monotonic()}
            if step["kind"] == "open":
                item["opening"] = first_opening if opened == 0 else "warm"
                opened += 1
            raw["phases"].append(item)
            if step.get("touch"):
                native_touch(plan["device"], *step["touch"])
                item["injection_end_monotonic_s"] = time.monotonic()
            if stop.wait(step["seconds"]):
                raise RuntimeError("monitor failed: " + str(raw["errors"]))
            item["end_monotonic_s"] = time.monotonic()
        raw["status"] = "CAPTURED_REQUIRES_REVIEW"
    except Exception as error:
        raw["errors"].append(str(error))
        raw["status"] = "FAILED"
    finally:
        stop.set()
        thread.join(timeout=2)
        raw["generation_unchanged"] = (read_generation(state_root) == generation
                                       and all(s["generation_sha256"] == gen_sha for s in raw["samples"]))
        raw["start_monotonic_s"], raw["end_monotonic_s"] = start, time.monotonic()
        try:  # journal after all timing samples, never during swipes
            text = subprocess.run(["journalctl", "-o", "json", "--since", "@" + str(epoch), "-u", "shell-ui.service",
                                   "-u", "theme-helper.service", "--no-pager"],
                                  capture_output=True, text=True, timeout=20, check=True).stdout
            for line in text.splitlines():
                entry = json.loads(line)
                message = entry.get("MESSAGE", "")
                if isinstance(message, str) and message.startswith("rust-shell "):
                    pid = entry.get("_PID")
                    raw["events"].append({"monotonic_us": entry.get("__MONOTONIC_TIMESTAMP"),
                                          "unit": entry.get("_SYSTEMD_UNIT"),
                                          "pid": int(pid) if str(pid).isdigit() else None, "message": message})
        except Exception as error:
            raw["errors"].append("journal collection failed: " + str(error))
            raw["status"] = "FAILED"
        output.write_text(json.dumps(raw, indent=2) + "\n")
    print(raw["status"], output)
    return 0 if raw["status"] == "CAPTURED_REQUIRES_REVIEW" and raw["generation_unchanged"] else 1


# --------------------------------------------------------------------- CLI

def main(argv=None) -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("validate")
    p.add_argument("plan", type=Path)
    p = sub.add_parser("preflight")
    p.add_argument("--plan", type=Path, required=True)
    p = sub.add_parser("capture")
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("reduce")
    p.add_argument("raw", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--rust-trace", type=Path, default=None,
                   help="Rust recorder report for this capture (required when instrumentation was on)")
    p = sub.add_parser("overhead")
    p.add_argument("off", type=Path)
    p.add_argument("on", type=Path)
    p = sub.add_parser("compare")
    p.add_argument("a", type=Path)
    p.add_argument("b", type=Path)
    p.add_argument("--vary", action="append", default=None,
                   help="field allowed to differ (default: rust_exe, current_system, booted_system)")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            errors = validate_plan(json.loads(args.plan.read_text()))
            for error in errors:
                print("plan error:", error, file=sys.stderr)
            return 1 if errors else 0
        if args.command == "preflight":
            _, _, failures, opening = preflight(load_plan(args.plan))
            print(json.dumps({"ok": not failures, "failures": failures, "first_opening": opening}, indent=2))
            return 1 if failures else 0
        if args.command == "capture":
            return capture(load_plan(args.plan), args.output)
        if args.command == "reduce":
            if args.output.exists():
                raise RuntimeError("refusing to overwrite evidence")
            trace = None
            if args.rust_trace is not None:
                if args.rust_trace.stat().st_size > MAX_TRACE_BYTES:
                    raise RuntimeError("Rust trace exceeds the telemetry size bound")
                trace = json.loads(args.rust_trace.read_text())
            report = reduce_raw(json.loads(args.raw.read_text()), trace)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            print(("OK " if report["comparable_inputs_valid"] else "GATES_FAILED ") + str(args.output))
            return 0 if report["comparable_inputs_valid"] else 1
        if args.command == "overhead":
            result = overhead_pair(json.loads(args.off.read_text()), json.loads(args.on.read_text()))
            print(json.dumps(result, indent=2))
            return 0 if result["comparable"] else 1
        vary = tuple(args.vary) if args.vary else DEFAULT_VARY
        result = compare_reports(json.loads(args.a.read_text()), json.loads(args.b.read_text()), vary)
        print(json.dumps(result, indent=2))
        return 0 if result["comparable"] else 1
    except (ValueError, RuntimeError, OSError) as error:
        print("theme-picker-profile:", error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
