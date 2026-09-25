#!/usr/bin/env python3
"""Capture per-frame timing and per-process CPU across one theme swap.

Runs ON the K230 board, as root (over the serial console), with the shell
user's own environment for the actual `k230-theme` invocation -- CPU/PID
sampling and `journalctl` both need privileges the `shell` user does not
have, but the swap itself must run exactly as the shell session would run
it. Writes one JSON report under `/run/` (never under the private
`XDG_RUNTIME_DIR` this instruments, to avoid recursively perturbing it).

This tool never synthesizes a board result: `--self-test` exercises its pure
parsing/analysis functions against fixtures and touches no PID, journal, or
`/run` file. A real capture always requires `--theme-id` and root.

See `tools/analyze-theme-swap-jank.py` for the host-side report -- this tool
only collects; it does not judge pass/fail.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path

SCHEMA = "k230-theme-swap-jank-v1"
CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
# journalctl -o json's MESSAGE field for the Rust shell's own event log
# (nix/rust-shell-client/src/main.rs's `fn log`): "rust-shell 981ms event-name"
RUST_LOG_RE = re.compile(r"^rust-shell (\d+)ms (\S.*)$")
# Card-shell (Sway) telemetry lines worth keeping as timeline context, from
# nix/card-shell/adapter.c's sway_log() calls -- never authoritative timing,
# only "what was happening" context around a gap.
SWAY_LOG_RE = re.compile(r"K230_CARD_SHELL\s+(\S+)")


def stat_cpu_ticks(stat_text: str) -> int | None:
    """Parse `/proc/<pid>/stat`'s utime+stime (fields 14, 15) in clock ticks.

    The comm field (field 2) is parenthesized and may itself contain spaces
    or parentheses, so fields are counted from the *last* ')' rather than by
    naive whitespace splitting.
    """
    end = stat_text.rfind(")")
    if end < 0:
        return None
    rest = stat_text[end + 1:].split()
    # rest[0] is field 3 (state); utime is field 14 -> rest[11], stime rest[12]
    if len(rest) < 13:
        return None
    try:
        return int(rest[11]) + int(rest[12])
    except ValueError:
        return None


def cpu_percent(delta_ticks: int, delta_wall_s: float) -> float:
    if delta_wall_s <= 0:
        return 0.0
    return max(0.0, min(100.0, 100.0 * (delta_ticks / CLK_TCK) / delta_wall_s))


class CpuSampler:
    """Polls `/proc/<pid>/stat` for a fixed pid set on a plain timer.

    Not a precise profiler (Python-loop jitter is itself tens of ms), but
    good enough to say which of a handful of long-lived board processes was
    burning CPU during a multi-hundred-ms to multi-second swap, which is the
    question this tool exists to answer. A pid that exits mid-capture simply
    stops contributing further samples.
    """

    def __init__(self, pids: dict[int, str], proc_root: Path = Path("/proc")):
        self.pids = dict(pids)  # pid -> label
        self.proc_root = proc_root
        self.samples: dict[int, list[dict]] = {pid: [] for pid in pids}
        self._last: dict[int, tuple[float, int]] = {}

    def add(self, pid: int, label: str) -> None:
        self.pids.setdefault(pid, label)
        self.samples.setdefault(pid, [])

    def poll(self, wall_s: float) -> None:
        for pid in list(self.pids):
            try:
                text = (self.proc_root / str(pid) / "stat").read_text()
            except OSError:
                continue
            ticks = stat_cpu_ticks(text)
            if ticks is None:
                continue
            previous = self._last.get(pid)
            self._last[pid] = (wall_s, ticks)
            if previous is None:
                continue
            previous_wall, previous_ticks = previous
            self.samples[pid].append({
                "wall_ms": round(wall_s * 1000, 1),
                "cpu_percent": round(cpu_percent(ticks - previous_ticks, wall_s - previous_wall), 2),
            })

    def summary(self) -> list[dict]:
        out = []
        for pid, label in self.pids.items():
            values = [s["cpu_percent"] for s in self.samples.get(pid, [])]
            out.append({
                "pid": pid,
                "label": label,
                "sample_count": len(values),
                "avg_cpu_percent": round(sum(values) / len(values), 2) if values else 0.0,
                "max_cpu_percent": round(max(values), 2) if values else 0.0,
            })
        return out


def main_pid(unit: str, systemctl: str = "systemctl") -> int | None:
    try:
        out = subprocess.run(
            [systemctl, "show", "-p", "MainPID", "--value", unit],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        pid = int(out)
    except ValueError:
        return None
    return pid or None


def theme_helper_pids(proc_root: Path = Path("/proc")) -> dict[int, str]:
    """Any live `k230-theme`/theme_catalog.py/omarchy-theme-set process.

    Used to attribute the ~1.2s-per-command Python start-up this task exists
    to measure and remove to a specific pid, not just "some CPU happened
    somewhere".
    """
    found: dict[int, str] = {}
    try:
        pids = [int(name) for name in os.listdir(proc_root) if name.isdigit()]
    except OSError:
        return found
    for pid in pids:
        try:
            cmdline = (proc_root / str(pid) / "cmdline").read_bytes()
        except OSError:
            continue
        text = cmdline.replace(b"\0", b" ").decode("utf-8", "replace")
        if re.search(r"theme_catalog\.py|theme_activate\.py|omarchy-theme-set|k230-theme\b", text):
            found[pid] = text.strip()[:120]
    return found


def journal_events(since_epoch: float, units: tuple[str, ...],
                    journalctl: str = "journalctl") -> list[dict]:
    """Read journal lines for `units` since `since_epoch`, tagged by source.

    Returns a wall-clock-ordered list of {wall_ms, source, event, raw}. Only
    lines recognisable as the Rust shell's own timestamped log or a
    `K230_CARD_SHELL` sway_log line become `event` entries; everything else
    from those units is kept as `raw` context only (never assumed to be a
    frame boundary).
    """
    try:
        out = subprocess.run(
            [journalctl, "-o", "json", "--since", f"@{since_epoch:.3f}",
             *sum((["-u", unit] for unit in units), [])],
            capture_output=True, text=True, timeout=15, check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    events = []
    for line in out.splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = entry.get("MESSAGE")
        if not isinstance(message, str):
            continue
        realtime_us = entry.get("__REALTIME_TIMESTAMP")
        try:
            wall_ms = int(realtime_us) / 1000.0
        except (TypeError, ValueError):
            continue
        unit = entry.get("_SYSTEMD_UNIT", "")
        match = RUST_LOG_RE.match(message)
        if match:
            events.append({"wall_ms": wall_ms, "source": "rust-shell",
                            "event": match.group(2), "raw": message})
            continue
        match = SWAY_LOG_RE.search(message)
        if match:
            events.append({"wall_ms": wall_ms, "source": "sway",
                            "event": match.group(1), "raw": message})
            continue
        events.append({"wall_ms": wall_ms, "source": unit or "journal",
                        "event": None, "raw": message})
    events.sort(key=lambda item: item["wall_ms"])
    return events


def run_theme_cli(shell_user: str, theme_command: str, theme_id: str,
                   runuser: str = "runuser", runtime_dir: str = "/run/shell") -> dict:
    """`k230-theme preview` then `activate`, exactly as the real chooser
    does, as `shell_user` with its session runtime directory (the helper
    socket lives there; plain `runuser` would not set it). `theme_id` may be
    the catalog's opaque id or a theme name, which is resolved via `list`."""
    import glob
    display = next((Path(p).name for p in sorted(glob.glob(runtime_dir + "/wayland-*"))
                    if not p.endswith(".lock")), None)
    env = ["env", "XDG_RUNTIME_DIR=" + runtime_dir] + (["WAYLAND_DISPLAY=" + display] if display else [])

    def call(*args: str) -> dict:
        result = subprocess.run(
            [runuser, "-u", shell_user, "--", *env, theme_command, *args],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return json.loads(result.stdout)

    if not re.fullmatch(r"[0-9a-f]{24}", theme_id):
        themes = call("list").get("themes", [])
        match = next((t for t in themes if theme_id in (t.get("name"), t.get("label"))), None)
        if match is None:
            raise ValueError(f"unknown theme {theme_id!r}")
        theme_id = match["id"]
    started = time.monotonic()
    preview = call("preview", "--json", theme_id)
    preview_ms = (time.monotonic() - started) * 1000
    generation = preview["generation"]
    started = time.monotonic()
    activate = call("activate", "--json", theme_id, "--expected-generation", generation)
    activate_ms = (time.monotonic() - started) * 1000
    return {"preview": preview, "activate": activate, "generation": generation,
            "theme_id": theme_id, "preview_ms": round(preview_ms, 1),
            "activate_ms": round(activate_ms, 1)}


def capture(args: argparse.Namespace) -> dict:
    sway_pid = main_pid(args.sway_unit, args.systemctl)
    rust_pid = main_pid(args.rust_unit, args.systemctl)
    sampler = CpuSampler({
        **({sway_pid: "sway"} if sway_pid else {}),
        **({rust_pid: "rust-shell"} if rust_pid else {}),
    })
    start_wall = time.time()
    deadline = time.monotonic() + args.duration_after_s
    tap_monotonic_ns = time.monotonic_ns()
    tap_wall_ms = time.time() * 1000

    # Poll in a tight loop around the swap itself so short-lived helper
    # processes (theme_catalog.py) are actually observed, not just sway/rust.
    helper_pids: dict[int, str] = {}
    activation_error = None
    activation_result = None

    def poll_once():
        sampler.poll(time.monotonic())
        for pid, cmd in theme_helper_pids().items():
            if pid not in helper_pids:
                helper_pids[pid] = cmd
                sampler.add(pid, f"helper:{cmd.split()[0] if cmd else pid}")

    poll_once()
    try:
        if args.activate_cmd:
            subprocess.run(args.activate_cmd, shell=True, check=True, timeout=30)
            activation_result = {"activate_cmd": args.activate_cmd}
        else:
            activation_result = run_theme_cli(args.shell_user, args.theme_command, args.theme_id,
                                              args.runuser)
    except (subprocess.SubprocessError, OSError, KeyError, json.JSONDecodeError) as error:
        activation_error = str(error)
    activate_done_wall_ms = time.time() * 1000
    poll_once()

    while time.monotonic() < deadline:
        time.sleep(0.02)
        poll_once()

    events = journal_events(start_wall, tuple(dict.fromkeys([args.sway_unit, args.rust_unit])),
                            args.journalctl)
    named_events = [event for event in events if event["event"] is not None
                    and event["wall_ms"] >= tap_wall_ms - 50]
    visible_wall_ms = next(
        (event["wall_ms"] for event in named_events
         if event["wall_ms"] >= tap_wall_ms and event["event"] in ("commit", "wallpaper-commit")),
        None,
    )

    return {
        "schema": SCHEMA,
        "theme_id": args.theme_id,
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start_wall)),
        "hostname": os.uname().nodename,
        "kernel_release": os.uname().release,
        "sway_pid": sway_pid,
        "rust_pid": rust_pid,
        "helper_pids": helper_pids,
        "tap_wall_ms": tap_wall_ms,
        "activate_done_wall_ms": activate_done_wall_ms,
        "visible_wall_ms": visible_wall_ms,
        "activation_result": activation_result,
        "activation_error": activation_error,
        "events": named_events,
        "cpu_samples": sampler.summary(),
    }


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--theme-id", help="theme id to activate, e.g. catppuccin-latte")
    parser.add_argument("--theme-command", default="/run/current-system/sw/bin/k230-theme")
    parser.add_argument("--shell-user", default="shell")
    parser.add_argument("--sway-unit", default="shell.service")
    parser.add_argument("--rust-unit", default="shell-ui.service")
    parser.add_argument("--systemctl", default="systemctl")
    parser.add_argument("--runuser", default="runuser")
    parser.add_argument("--journalctl", default="journalctl")
    parser.add_argument("--duration-after-s", type=float, default=3.0,
                        help="keep sampling/collecting this long after activate returns, "
                             "to catch trailing keyboard/foot recolour and settle frames")
    parser.add_argument("--activate-cmd",
                        help="run this shell command instead of the default preview+activate "
                             "pair -- e.g. a persistent-helper CLI under evaluation")
    parser.add_argument("--out", type=Path,
                        default=Path(f"/run/theme-swap-jank-{int(time.time())}.json"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if not args.self_test and not args.theme_id:
        parser.error("--theme-id is required (or pass --self-test)")
    return args


class ParserTests(unittest.TestCase):
    def test_stat_cpu_ticks_parses_fields_past_a_parenthesized_comm(self):
        # comm can contain spaces/parens; only the state field onward is
        # positional after the *last* ')'.
        fields = ["0", "(k230 (shell))", "S"] + ["0"] * 10 + ["123", "45"] + ["0"] * 30
        self.assertEqual(stat_cpu_ticks(" ".join(fields)), 168)

    def test_stat_cpu_ticks_rejects_a_short_line(self):
        self.assertIsNone(stat_cpu_ticks("1 (x) S 0 0"))

    def test_cpu_percent_is_bounded_and_handles_zero_wall_time(self):
        self.assertEqual(cpu_percent(0, 0.0), 0.0)
        self.assertEqual(cpu_percent(CLK_TCK, 1.0), 100.0)
        self.assertEqual(cpu_percent(CLK_TCK * 10, 1.0), 100.0)  # clamped

    def test_cpu_sampler_computes_percent_between_two_polls(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pid_dir = root / "42"
            pid_dir.mkdir()
            fields = ["(x)", "S"] + ["0"] * 10 + ["100", "0"] + ["0"] * 30
            (pid_dir / "stat").write_text("42 " + " ".join(fields))
            sampler = CpuSampler({42: "test"}, proc_root=root)
            sampler.poll(0.0)
            fields = ["(x)", "S"] + ["0"] * 10 + ["150", "0"] + ["0"] * 30
            (pid_dir / "stat").write_text("42 " + " ".join(fields))
            sampler.poll(0.5)
            summary = sampler.summary()[0]
            self.assertEqual(summary["sample_count"], 1)
            self.assertAlmostEqual(summary["avg_cpu_percent"], 100.0, delta=0.1)

    def test_journal_events_tags_rust_and_sway_lines_and_keeps_others_as_context(self):
        payload = "\n".join(json.dumps(entry) for entry in [
            {"MESSAGE": "rust-shell 981ms wallpaper-commit", "__REALTIME_TIMESTAMP": "1000000",
             "_SYSTEMD_UNIT": "shell-ui.service"},
            {"MESSAGE": "00:00:31.984 [DEBUG] [sway/card_shell.c:1299] K230_CARD_SHELL state mode=0",
             "__REALTIME_TIMESTAMP": "1010000", "_SYSTEMD_UNIT": "shell.service"},
            {"MESSAGE": "some unrelated line", "__REALTIME_TIMESTAMP": "1020000",
             "_SYSTEMD_UNIT": "shell.service"},
        ])

        class FakeCompleted:
            stdout = payload

        def fake_run(*_args, **_kwargs):
            return FakeCompleted()

        # journal_events shells out to journalctl; patch subprocess.run for
        # this call only, then always restore it.
        real_run = subprocess.run
        subprocess.run = fake_run
        try:
            events = journal_events(0.0, ("shell.service", "shell-ui.service"))
        finally:
            subprocess.run = real_run
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["source"], "rust-shell")
        self.assertEqual(events[0]["event"], "wallpaper-commit")
        self.assertEqual(events[1]["source"], "sway")
        self.assertEqual(events[1]["event"], "state")
        self.assertIsNone(events[2]["event"])


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ParserTests)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    if os.geteuid() != 0:
        print("theme-swap-jank: must run as root (CPU sampling and journalctl need it)",
              file=sys.stderr)
        return 2
    report = capture(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(str(args.out))
    return 0 if report["activation_error"] is None else 1


if __name__ == "__main__":
    sys.exit(main())
