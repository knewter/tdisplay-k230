#!/usr/bin/env python3
"""Run or plan the injected-input acceptance sequence for launcher gestures.

This program runs on the board only when --execute is supplied.  It calls the
existing inject-tap.sh uinput helper, so all resulting evidence is explicitly
labelled injected-pointer evidence.  It cannot establish glass/finger accuracy.
"""

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

PANEL_WIDTH = 568
PANEL_HEIGHT = 1232
CARD_Y = 320
LEFT_START = (430, CARD_Y)
LEFT_END = (130, CARD_Y)
UP_START = (284, 460)
UP_END = (284, 210)
BACK = (284, 1165)


def shell(command: str, *, execute: bool) -> None:
    if execute:
        subprocess.run(["sh", "-c", command], check=True)


def capture(grim: str, path: Path, *, execute: bool) -> None:
    if execute:
        subprocess.run([grim, str(path)], check=True)


def inject(script: str, device: str, start: tuple[int, int], end: tuple[int, int], *, execute: bool) -> list[str]:
    command = [script, device, str(start[0]), str(start[1]), str(end[0]), str(end[1])]
    if execute:
        subprocess.run(command, check=True)
    return command


def resource_snapshot(pid: int | None) -> dict[str, str]:
    if pid is None:
        return {"status": "not-requested"}
    root = Path(f"/proc/{pid}")
    if not root.is_dir():
        return {"status": "pid-not-found", "pid": str(pid)}
    result: dict[str, str] = {"status": "captured", "pid": str(pid)}
    for filename, wanted in (("status", {"VmRSS:", "VmHWM:"}), ("smaps_rollup", {"Pss:", "Rss:"})):
        try:
            lines = root.joinpath(filename).read_text().splitlines()
        except OSError as error:
            result[filename] = f"unavailable: {error}"
            continue
        result[filename] = "\n".join(line for line in lines if line.split(maxsplit=1)[0] in wanted)
    return result


def command_output(command: str | None, *, execute: bool) -> tuple[int | None, str]:
    if not command:
        return None, "not-requested"
    if not execute:
        return None, "planned-only"
    completed = subprocess.run(["sh", "-c", command], text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    return completed.returncode, completed.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, help="uinput touch device accepted by inject-tap.sh")
    parser.add_argument("--inject-script", default="tools/inject-tap.sh")
    parser.add_argument("--grim", default="grim", help="board grim executable")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--launcher-pid", type=int, help="launcher PID for /proc memory snapshots")
    parser.add_argument("--metrics-file", type=Path,
                        help="optional K230_LAUNCHER_METRICS file to copy into evidence")
    parser.add_argument("--keyboard-command", help="board command that shows keyboard before its native capture")
    parser.add_argument("--window-catalog-command", help="read-only command producing one TSV row per window")
    parser.add_argument("--prepare-command", help="optional board command to open Apps before injection")
    parser.add_argument("--execute", action="store_true", help="perform board commands; otherwise write a plan only")
    args = parser.parse_args()

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output_dir or Path("docs/evidence/launcher-gestures") / stamp
    output.mkdir(parents=True, exist_ok=True)
    if args.execute and not args.keyboard_command:
        parser.error("--keyboard-command is required with --execute so the keyboard-visible capture is meaningful")
    if args.execute and not args.window_catalog_command:
        parser.error("--window-catalog-command is required with --execute to prove a multi-card overview")
    if args.execute and not Path(args.inject_script).is_file():
        parser.error(f"inject script not found: {args.inject_script}")

    plan: list[dict[str, Any]] = []
    plan.append({"step": "prepare", "command": args.prepare_command or "operator opens Apps", "provenance": "injected"})
    shell(args.prepare_command, execute=args.execute) if args.prepare_command else None
    capture(args.grim, output / "apps-before.png", execute=args.execute)

    # Alternate directions. Every swipe begins in a card, so it exercises one
    # left and one right transition without relying on an unbounded page count.
    for index in range(1, 21):
        plan.append({"step": "left-swipe", "index": index,
                     "command": inject(args.inject_script, args.device, LEFT_START, LEFT_END, execute=args.execute)})
        plan.append({"step": "right-swipe", "index": index,
                     "command": inject(args.inject_script, args.device, LEFT_END, LEFT_START, execute=args.execute)})
    capture(args.grim, output / "after-20-each.png", execute=args.execute)

    if args.keyboard_command:
        plan.append({"step": "keyboard-visible", "command": args.keyboard_command})
        shell(args.keyboard_command, execute=args.execute)
        capture(args.grim, output / "keyboard-visible.png", execute=args.execute)
    else:
        plan.append({"step": "keyboard-visible", "status": "requires --keyboard-command"})

    code, catalog = command_output(args.window_catalog_command, execute=args.execute)
    rows = [line for line in catalog.splitlines() if line.strip()] if code == 0 else []
    plan.append({"step": "window-catalog", "command": args.window_catalog_command or "not-requested",
                 "exit_status": code, "row_count": len(rows) if code == 0 else None})
    if args.execute and args.window_catalog_command:
        (output / "window-catalog.tsv").write_text(catalog)
        if code != 0 or len(rows) < 2:
            print("need at least two current windows for the multi-card overview", file=sys.stderr)
            return 1

    plan.append({"step": "overview-up", "command": inject(args.inject_script, args.device, UP_START, UP_END, execute=args.execute)})
    capture(args.grim, output / "overview.png", execute=args.execute)
    plan.append({"step": "button-recovery-back", "command": inject(args.inject_script, args.device, BACK, BACK, execute=args.execute)})
    capture(args.grim, output / "after-back.png", execute=args.execute)

    metrics_status = "not-requested"
    if args.execute and args.metrics_file:
        try:
            (output / "launcher-metrics.txt").write_text(args.metrics_file.read_text())
            metrics_status = "copied"
        except OSError as error:
            metrics_status = f"unavailable: {error}"

    report = {
        "captured_at_utc": stamp,
        "interaction_provenance": "injected-pointer",
        "provenance_note": "uinput injection and native screencopy do not prove a physical finger touched the glass.",
        "panel": {"width": PANEL_WIDTH, "height": PANEL_HEIGHT},
        "requested": {"left_swipes": 20, "right_swipes": 20, "keyboard_capture": True,
                      "overview_capture": True, "button_recovery_capture": True},
        "window_catalog_rows": len(rows) if code == 0 else None,
        "launcher_resources_before": resource_snapshot(args.launcher_pid) if args.execute else {"status": "planned-only"},
        "launcher_resources_after": resource_snapshot(args.launcher_pid) if args.execute else {"status": "planned-only"},
        "metrics_copy": metrics_status,
        "steps": plan,
        "metrics_note": "Set K230_LAUNCHER_METRICS before launching the native client, then copy that file into this directory. The client records wall-clock render and release-to-submit intervals, not process CPU time or scanout timing.",
        "real_finger_gate": "Open after this injected acceptance: capture a separate focused camera trial with actual left/right/up/down gestures and a card tap."
    }
    (output / "acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {output / 'acceptance.json'}")
    if not args.execute:
        print("plan only: no board command, uinput event, grim capture, or physical-touch assertion was made")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
