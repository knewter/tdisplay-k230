"""Manifest, per-run metrics and decision logic for the Qt Quick / Quickshell trial.

Pure functions; no board access. Evidence classes stay explicit: every run
records `boundary: client_commit` (the client's own wl_surface.commit or Qt
frame-swap), which is submission, never presentation or optical latency.
"""
from collections import OrderedDict
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SCHEMA = "qtquick-trial-manifest/1"
RUN_SCHEMA = "qtquick-run/1"
BUDGET_VERSION = "qtq-budgets-1"
WORKLOAD_ID = "qtq-workload-1"

# Proposed trial ceilings from design.md decision 5, frozen before any run.
CEILINGS = OrderedDict([
    ("startup_ms", 5000),
    ("incremental_memory_mib", 128),
    ("idle_client_cpu_pct", 2.0),
    ("regression_report_pct", 10.0),
])
WORKLOAD = OrderedDict([
    ("id", WORKLOAD_ID),
    ("viewport", [568, 1232]),
    ("scale", 1),
    ("pairs", 3),
    ("idle_s", 30),
    ("active_s", 30),
    ("min_interactions", 24),
    ("order", "ABBA-style alternation: pair 1 qt then baseline, pair 2 baseline then qt, pair 3 qt then baseline"),
    ("boundary", "client_commit"),
])
TOOLKITS = ("qt", "baseline")
BINARIES = {"qt": "bin/qtquick-software-probe", "baseline": "bin/qtquick-shm-baseline"}
STORE_RE = re.compile(r"^/nix/store/[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._-]+$")
EVENT_KINDS = {"press", "move", "release", "key"}


def card_budgets():
    """The unchanged card budgets, read from the card benchmark so they cannot drift here."""
    spec = importlib.util.spec_from_file_location("card_shell_benchmark", ROOT / "tools/card-shell-benchmark.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return json.loads(json.dumps(module.BUDGETS))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def manifest_hash(manifest):
    body = {k: v for k, v in manifest.items() if k != "hash"}
    return digest(body)


class ManifestError(ValueError):
    pass


def check_artifact(name, artifact):
    if not isinstance(artifact, dict):
        raise ManifestError(f"{name}: artifact record missing")
    path = artifact.get("store_path")
    if not isinstance(path, str) or not STORE_RE.match(path):
        raise ManifestError(f"{name}: store_path is not a Nix store directory")
    if artifact.get("binary") != BINARIES[name]:
        raise ManifestError(f"{name}: binary must be {BINARIES[name]}")
    for key in ("closure_bytes", "closure_paths", "nar_bytes"):
        if not isinstance(artifact.get(key), int) or artifact[key] <= 0:
            raise ManifestError(f"{name}: {key} missing")


def validate_manifest(manifest):
    """Reject anything that is not exactly the frozen plan; returns the manifest."""
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ManifestError("unknown manifest schema")
    if manifest.get("hash") != manifest_hash(manifest):
        raise ManifestError("manifest hash does not match its contents")
    if manifest.get("budget_version") != BUDGET_VERSION:
        raise ManifestError("budget version changed without a new frozen version")
    if manifest.get("ceilings") != CEILINGS:
        raise ManifestError("ceilings changed from the frozen values")
    if manifest.get("card_budgets") != card_budgets():
        raise ManifestError("card budgets differ from tools/card-shell-benchmark.py")
    if manifest.get("workload") != WORKLOAD:
        raise ManifestError("workload differs from the frozen workload")
    artifacts = manifest.get("artifacts", {})
    for name in TOOLKITS:
        check_artifact(name, artifacts.get(name))
    if artifacts["qt"]["store_path"] == artifacts["baseline"]["store_path"]:
        raise ManifestError("qt and baseline must be different artifacts")
    system = manifest.get("system", {})
    for key in ("toplevel", "compositor"):
        if not isinstance(system.get(key), str) or not STORE_RE.match(system[key]):
            raise ManifestError(f"system.{key} must be a Nix store path")
    return manifest


def build_manifest(created_utc, qt, baseline, system, source):
    manifest = OrderedDict([
        ("schema", MANIFEST_SCHEMA),
        ("budget_version", BUDGET_VERSION),
        ("created_utc", created_utc),
        ("ceilings", CEILINGS),
        ("card_budgets", card_budgets()),
        ("workload", WORKLOAD),
        ("artifacts", {"qt": qt, "baseline": baseline}),
        ("system", system),
        ("source", source),
    ])
    manifest = json.loads(json.dumps(manifest))
    manifest["hash"] = manifest_hash(manifest)
    return manifest


# ---- per-run metrics ------------------------------------------------------
def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round(q * (len(ordered) - 1)))))
    return ordered[index]


def parse_events(text):
    """Bounded JSONL; unknown lines are ignored, never trusted for identity."""
    events = []
    for line in text.splitlines()[:50000]:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and isinstance(row.get("e"), str) and isinstance(row.get("t"), int):
            events.append(row)
    return events


def input_to_commit(events, window):
    """Latency from each input receipt to the next commit; (start, end) ms window."""
    lo, hi = window
    commits = [e["t"] for e in events if e["e"] == "commit"]
    out = []
    for e in events:
        if e["e"] != "input" or not lo <= e["t"] < hi or e.get("k") not in EVENT_KINDS:
            continue
        later = [c for c in commits if c >= e["t"]]
        if later:
            out.append(later[0] - e["t"])
    return out


def commit_gaps(events, window):
    lo, hi = window
    times = [e["t"] for e in events if e["e"] == "commit" and lo <= e["t"] < hi]
    return [b - a for a, b in zip(times, times[1:])]


def analyse_run(run, events):
    """Metrics for one run. Anything unmeasurable is None and marks the run incomplete."""
    missing = []
    ph = run.get("phases", {})

    def cpu_pct(phase, key):
        p = ph.get(phase)
        if not p or not p.get("elapsed_s") or p.get(key) is None:
            missing.append(f"{phase}.{key}")
            return None
        return 100.0 * p[key] / 1e6 / p["elapsed_s"]

    first = [e["t"] for e in events if e["e"] == "first_frame"]
    startup = first[0] - run["launch_mono_ms"] if first and run.get("launch_mono_ms") else None
    if startup is None:
        missing.append("first_frame")
    active = ph.get("active", {})
    window = (active.get("start_mono_ms", 0), active.get("end_mono_ms", 0))
    latencies = input_to_commit(events, window) if window[1] else []
    unmatched = len([e for e in events if e["e"] == "input" and window[0] <= e["t"] < window[1]]) - len(latencies)
    inputs = len([e for e in events if e["e"] == "input" and window[0] <= e["t"] < window[1]])
    if not latencies:
        missing.append("presentation_samples")
    if unmatched > max(1, inputs // 10):
        missing.append("unmatched_inputs")
    gaps = commit_gaps(events, window) if window[1] else []
    mem = run.get("memory", {})
    delta = None
    if mem.get("before_kib") is not None and mem.get("active_used_kib") is not None:
        delta = (mem["active_used_kib"] - mem["before_kib"]) / 1024.0
    else:
        missing.append("memory")
    idle_client = cpu_pct("idle", "client_cpu_us")
    idle_sway = cpu_pct("idle", "sway_cpu_us")
    active_client = cpu_pct("active", "client_cpu_us")
    active_sway = cpu_pct("active", "sway_cpu_us")
    interactions = run.get("interactions", [])
    metrics = OrderedDict([
        ("startup_ms", startup),
        ("incremental_memory_mib", delta),
        ("idle_client_cpu_pct", idle_client),
        ("idle_sway_cpu_pct", idle_sway),
        ("idle_combined_cpu_pct", None if idle_client is None or idle_sway is None else idle_client + idle_sway),
        ("active_client_cpu_pct", active_client),
        ("active_sway_cpu_pct", active_sway),
        ("active_combined_cpu_pct", None if active_client is None or active_sway is None else active_client + active_sway),
        ("input_to_commit_p50_ms", percentile(latencies, 0.5)),
        ("input_to_commit_p95_ms", percentile(latencies, 0.95)),
        ("input_to_commit_max_ms", max(latencies) if latencies else None),
        ("input_samples", len(latencies)),
        ("commit_gap_p95_ms", percentile(gaps, 0.95)),
        ("commit_gap_max_ms", max(gaps) if gaps else None),
        ("interactions", len(interactions)),
        ("injector_cpu_s", run.get("injector_cpu_s")),
    ])
    if len(interactions) < WORKLOAD["min_interactions"]:
        missing.append("interactions")
    return {"metrics": metrics, "missing": sorted(set(missing)), "boundary": "client_commit"}


def ceiling_results(metrics):
    out = OrderedDict()
    for key, limit in (("startup_ms", CEILINGS["startup_ms"]),
                       ("incremental_memory_mib", CEILINGS["incremental_memory_mib"]),
                       ("idle_client_cpu_pct", CEILINGS["idle_client_cpu_pct"])):
        value = metrics.get(key)
        out[key] = {"limit": limit, "value": value,
                    "status": "INCOMPLETE" if value is None else ("PASS" if value <= limit else "FAIL")}
    return out


FUNCTIONAL_GATES = (
    "software_route",      # env/QSG_INFO/mapped libs/WAYLAND_DEBUG identify software + wl_shm
    "pixels_correct",      # native capture matches the expected scene
    "scroll",              # injected drag moved the list
    "tap",                 # injected tap changed the selected row / mover
    "interrupted_motion",  # a tap while the mover animates retargets it
    "text_focus",          # tapping the field enabled text input and showed the keyboard
    "text_entry",          # entered text appeared in the field
    "readable",            # capture crop of the text is distinguishable from the background
    "bounded_lifetime",    # the process ended inside its deadline
    "restored",            # normal shell identity and focus returned
)


def functional_results(run):
    rec = run.get("functional", {})
    out = OrderedDict()
    for gate in FUNCTIONAL_GATES:
        value = rec.get(gate)
        out[gate] = "INCOMPLETE" if value is None else ("PASS" if value else "FAIL")
    return out


def mean_sd(values):
    values = [v for v in values if v is not None]
    if not values:
        return None, None
    return statistics.fmean(values), (statistics.pstdev(values) if len(values) > 1 else 0.0)


def compare(qt_runs, base_runs, baseline_ok):
    """Per-pair differences; a failed or noisy baseline makes the comparison INCONCLUSIVE."""
    rows = OrderedDict()
    for key in ("active_combined_cpu_pct", "input_to_commit_p95_ms", "idle_combined_cpu_pct", "startup_ms"):
        pairs = []
        for q, b in zip(qt_runs, base_runs):
            qv, bv = q["metrics"].get(key), b["metrics"].get(key)
            if qv is None or bv is None:
                pairs = None
                break
            pairs.append((qv, bv))
        if pairs is None or not pairs:
            rows[key] = {"status": "INCOMPLETE"}
            continue
        qm, qs = mean_sd([p[0] for p in pairs])
        bm, bs = mean_sd([p[1] for p in pairs])
        regression = None if not bm else 100.0 * (qm - bm) / bm
        noisy = bool(bm) and bs is not None and bs > 0.5 * bm
        status = "INCONCLUSIVE" if (not baseline_ok or noisy) else (
            "REGRESSION" if regression is not None and regression > CEILINGS["regression_report_pct"] else "WITHIN_10_PCT")
        rows[key] = {"qt_mean": qm, "qt_sd": qs, "baseline_mean": bm, "baseline_sd": bs,
                     "regression_pct": regression, "pairs": pairs, "status": status,
                     "baseline_noisy": noisy}
    return rows


def evaluate_stage(manifest, runs, restorations):
    """runs: list of {'run': run-record, 'events': [..]}. Returns the decision record."""
    validate_manifest(manifest)
    problems = []
    analysed = {t: [] for t in TOOLKITS}
    for item in sorted(runs, key=lambda r: (r["run"].get("pair", 0), r["run"].get("order", 0))):
        run = item["run"]
        if run.get("schema") != RUN_SCHEMA:
            problems.append(f"run schema {run.get('schema')!r}")
            continue
        if run.get("manifest_hash") != manifest["hash"]:
            problems.append(f"pair {run.get('pair')} {run.get('toolkit')}: manifest hash mismatch")
            continue
        if run.get("toolkit") not in TOOLKITS:
            problems.append("unknown toolkit")
            continue
        artifact = manifest["artifacts"][run["toolkit"]]["store_path"]
        if run.get("artifact") != artifact:
            problems.append(f"pair {run.get('pair')} {run['toolkit']}: artifact id mismatch")
            continue
        result = analyse_run(run, item["events"])
        result["pair"] = run["pair"]
        result["ceilings"] = ceiling_results(result["metrics"])
        result["functional"] = functional_results(run)
        analysed[run["toolkit"]].append(result)
    pairs = WORKLOAD["pairs"]
    for t in TOOLKITS:
        if sorted(r["pair"] for r in analysed[t]) != list(range(1, pairs + 1)):
            problems.append(f"{t}: expected pairs 1..{pairs}, got {sorted(r['pair'] for r in analysed[t])}")
    restored = bool(restorations) and all(r.get("ok") for r in restorations)
    if not restorations:
        problems.append("no restoration records")
    elif not restored:
        problems.append("a restoration check failed")
    base_func_fail = [g for r in analysed["baseline"] for g, v in r["functional"].items()
                      if v == "FAIL" and g in ("pixels_correct", "scroll", "tap", "bounded_lifetime", "restored")]
    baseline_ok = not base_func_fail and all(not r["missing"] for r in analysed["baseline"]) and \
        len(analysed["baseline"]) == pairs
    qt = sorted(analysed["qt"], key=lambda r: r["pair"])
    base = sorted(analysed["baseline"], key=lambda r: r["pair"])
    criteria = OrderedDict()
    for gate in FUNCTIONAL_GATES:
        states = [r["functional"][gate] for r in qt]
        if not qt:
            states = ["INCOMPLETE"]
        criteria[f"functional.{gate}"] = ("FAIL" if "FAIL" in states else
                                          "INCOMPLETE" if "INCOMPLETE" in states else "PASS")
    for key in ("startup_ms", "incremental_memory_mib", "idle_client_cpu_pct"):
        states = [r["ceilings"][key]["status"] for r in qt] or ["INCOMPLETE"]
        criteria[f"ceiling.{key}"] = ("FAIL" if "FAIL" in states else
                                      "INCOMPLETE" if "INCOMPLETE" in states else "PASS")
    criteria["measurements_complete"] = "PASS" if qt and all(not r["missing"] for r in qt) and not problems else "INCOMPLETE"
    criteria["baseline_control"] = "PASS" if baseline_ok else ("FAIL" if base_func_fail else "INCOMPLETE")
    states = list(criteria.values())
    overall = "FAIL" if "FAIL" in states else ("INCOMPLETE" if "INCOMPLETE" in states or problems else "PASS")
    return OrderedDict([
        ("schema", "qtquick-decision/1"),
        ("manifest_hash", manifest["hash"]),
        ("overall", overall),
        ("criteria", criteria),
        ("problems", problems),
        ("runs", {t: analysed[t] for t in TOOLKITS}),
        ("comparison", compare(qt, base, baseline_ok)),
        ("production_budget", OrderedDict([
            ("status", "NOT_ASSESSED"),
            ("reason", "This trial measures a minimal app against a matched client; the card budgets "
                       "(frame CPU p95 16.667 ms, tracking interval p95 33.334 ms, 64 MiB) are unchanged and "
                       "a passing prerequisite does not certify them."),
            ("card_budgets", manifest["card_budgets"]),
        ])),
        ("boundary", "client_commit: submission only; not presentation or optical input-to-photon latency"),
    ])
