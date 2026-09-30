#!/usr/bin/env python3
"""Run the real opt-in Pixman quarter-turn compositor against an animated SHM client.

This is headless QEMU evidence. It exercises pixels and Wayland liveness on an
actual Sway/wlroots scene; it does not establish physical HDMI or touch behavior.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import struct
import subprocess
import tempfile
import time

from PIL import Image, ImageChops


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def wait_for(predicate, timeout=30, description="condition"):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {description}")


def latest_client_state(path):
    states = []
    if path.exists():
        for line in path.read_text(errors="replace").splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if value.get("event") in ("heartbeat", "commit", "child_commit"):
                states.append(value)
    return states[-1] if states else None


def ipc(runtime, command, kind=0, check=True):
    sock = socket.socket(socket.AF_UNIX)
    sock.settimeout(10)
    sock.connect(str(next(runtime.glob("sway-ipc.*.sock"))))
    payload = command.encode()
    sock.sendall(b"i3-ipc" + struct.pack("=II", len(payload), kind) + payload)

    def read(size):
        chunks = bytearray()
        while len(chunks) < size:
            block = sock.recv(size - len(chunks))
            if not block:
                raise AssertionError("Sway IPC closed before completing a response")
            chunks.extend(block)
        return bytes(chunks)

    header = read(14)
    length, _ = struct.unpack("=II", header[6:])
    response = json.loads(read(length))
    sock.close()
    if kind == 0 and check:
        assert all(row.get("success") for row in response), (command, response)
    return response


def capture(env, path):
    subprocess.run(["grim", str(path)], env=env, check=True, timeout=20)
    with Image.open(path) as opened:
        return opened.convert("RGB")


def assert_live_between(before, after, label):
    assert before and after, f"{label}: client emitted no frame counters"
    for plane in ("", "child_"):
        for field in ("frames", "callbacks", "releases"):
            key = plane + field
            assert after[key] > before[key], (
                f"{label}: {key} did not advance: {before[key]} -> {after[key]}"
            )


def run_variant(args, output, name, transform, quarter_turn):
    runtime = output / name
    runtime.mkdir(mode=0o700)
    config = runtime / "sway.conf"
    config.write_text(
        f"output * mode 1920x1080 transform {transform}\n"
        "seat seat0 fallback true\n"
        "focus_follows_mouse no\n"
        'for_window [app_id="^k230.card."] card_shell ordinary, floating enable, '
        "border none, resize set 100 ppt 100 ppt, move position 0 0\n"
    )
    env = dict(
        os.environ,
        XDG_RUNTIME_DIR=str(runtime),
        WLR_BACKENDS="headless",
        WLR_HEADLESS_OUTPUTS="1",
        WLR_RENDERER="pixman",
        WLR_PIXMAN_QUARTER_TURN="1" if quarter_turn else "0",
        WLR_PIXMAN_OUTPUT_TURN="0",
        WLR_PIXMAN_DRAW_TRACE="1",
        SWAY_K230_CARD_SHELL="1",
        SWAY_K230_CARD_TOUCH_FIRST="1",
        SWAY_K230_CARD_TEST_INPUT="1",
    )
    children = []
    streams = []
    result = {"name": name, "transform": str(transform),
              "quarter_turn_enabled": bool(quarter_turn), "captures": {},
              "client_states": {}}
    sway_log = (runtime / "sway.log").open("w")
    sway = subprocess.Popen(
        [args.qemu, str(args.sway), "-c", str(config), "-d"],
        env=env, stdout=sway_log, stderr=sway_log,
    )
    children.append(sway)
    try:
        wait_for(lambda: "Running compositor on wayland display" in
                 (runtime / "sway.log").read_text(errors="replace"),
                 timeout=60, description=f"{name} compositor startup")
        env["WAYLAND_DISPLAY"] = next(
            path.name for path in runtime.glob("wayland-*")
            if not path.name.endswith(".lock")
        )
        outputs = ipc(runtime, "", 3)
        headless = next(row for row in outputs if row.get("name") == "HEADLESS-1")
        expected_rect = {"x": 0, "y": 0,
                         "width": 1080 if transform in ("90", "270") else 1920,
                         "height": 1920 if transform in ("90", "270") else 1080}
        assert headless["current_mode"] == {"width": 1920, "height": 1080,
                                             "refresh": 0}, headless
        assert str(headless["transform"]) == transform, headless
        assert headless["scale"] == 1.0, headless
        assert headless["rect"] == expected_rect, headless
        result["output"] = {key: headless[key] for key in
                            ("name", "current_mode", "transform", "scale", "rect")}

        app_log = runtime / "client.jsonl"
        stream = app_log.open("w")
        streams.append(stream)
        client = subprocess.Popen(
            [str(args.client), "--app-id", "k230.card.one", "--duration", "120"],
            env=env, stdout=stream, stderr=stream,
        )
        children.append(client)
        wait_for(lambda: latest_client_state(app_log), timeout=20,
                 description=f"{name} initial client frame")
        wait_for(lambda: (state if (state := latest_client_state(app_log)) and
                               state["frames"] >= 8 else None),
                 timeout=20, description=f"{name} ordinary client frames")
        ordinary_before = latest_client_state(app_log)
        ordinary_a = capture(env, runtime / "ordinary-a.png")
        time.sleep(0.8)
        ordinary_b = capture(env, runtime / "ordinary-b.png")
        ordinary_after = wait_for(
            lambda: (state if (state := latest_client_state(app_log)) and
                     state["frames"] > ordinary_before["frames"] else None),
            timeout=10, description=f"{name} ordinary frame progress",
        )
        assert_live_between(ordinary_before, ordinary_after, f"{name} ordinary")
        assert ImageChops.difference(ordinary_a, ordinary_b).getbbox(), (
            f"{name}: ordinary scene pixels stayed static while client counters advanced"
        )
        result["client_states"]["ordinary_before"] = ordinary_before
        result["client_states"]["ordinary_after"] = ordinary_after
        result["captures"]["ordinary"] = {
            "a": {"file": "ordinary-a.png", "sha256": digest(runtime / "ordinary-a.png"),
                  "size": list(ordinary_a.size)},
            "b": {"file": "ordinary-b.png", "sha256": digest(runtime / "ordinary-b.png"),
                  "size": list(ordinary_b.size)},
        }

        if transform == "180":
            # The renderer's ordinary scene still exercises the unmodified
            # transform sampler. The current card-shell UI guard declines to
            # initialize at 180 degrees, so do not mislabel an overview as
            # covered for this fallback-only orientation.
            response = ipc(runtime, "card_shell enter", check=False)
            assert response and not response[0].get("success") and \
                response[0].get("error") == "card shell requires one Pixman output", response
            result["overview"] = {
                "status": "unavailable-at-transform-180",
                "ipc_response": response,
            }
        else:
            # Replay the exact y==height contact observed on physical HDMI.
            # This is injected headless proof of the real adapter/policy path.
            width, height = expected_rect["width"], expected_rect["height"]
            down = ipc(runtime, f"card_shell down 91 {width / 2} {height}")
            ipc(runtime, f"card_shell motion 91 {width / 2} {height - 300}")
            ipc(runtime, "card_shell up 91")
            time.sleep(0.5)
            ipc(runtime, "card_shell back")
            result["exact_bottom_endpoint"] = {
                "evidence_class": "headless-qemu-injected-input",
                "x": width / 2, "y": height, "down_response": down,
            }
            response = ipc(runtime, "card_shell enter")
            result["overview"] = {"status": "entered", "ipc_response": response}
        if transform != "180":
            time.sleep(2.0)
            overview_before = latest_client_state(app_log)
            overview_a = capture(env, runtime / "overview-a.png")
            time.sleep(0.8)
            overview_b = capture(env, runtime / "overview-b.png")
            overview_after = wait_for(
                lambda: (state if (state := latest_client_state(app_log)) and
                         state["frames"] > overview_before["frames"] else None),
                timeout=10, description=f"{name} overview frame progress",
            )
            assert_live_between(overview_before, overview_after, f"{name} overview")
            assert ImageChops.difference(overview_a, overview_b).getbbox(), (
                f"{name}: overview scene pixels stayed static while client counters advanced"
            )
            result["client_states"]["overview_before"] = overview_before
            result["client_states"]["overview_after"] = overview_after
            result["captures"]["overview"] = {
                "a": {"file": "overview-a.png", "sha256": digest(runtime / "overview-a.png"),
                      "size": list(overview_a.size)},
                "b": {"file": "overview-b.png", "sha256": digest(runtime / "overview-b.png"),
                      "size": list(overview_b.size)},
            }

        trace = (runtime / "sway.log").read_text(errors="replace")
        draw_rows = re.findall(
            r"K230_PIXMAN_DRAW transform=(\d+) path=(tiled|sampler) "
            r"copy_cpu_ns=(\d+) total_cpu_ns=(\d+) dst_pixels=(\d+) scratch_bytes=(\d+)",
            trace,
        )
        assert draw_rows, f"{name}: no candidate draw trace rows found"
        # Sway interprets CLI degrees clockwise and inverts them before
        # storing the Wayland anti-clockwise enum (90=1, 180=2, 270=3).
        expected_transform = {"90": "3", "180": "2", "270": "1"}[transform]
        matching = [(path, int(copy), int(total), int(pixels), int(scratch))
                    for turn, path, copy, total, pixels, scratch in draw_rows
                    if turn == expected_transform]
        assert matching, f"{name}: no draw rows for output transform {transform}"
        paths = sorted({row[0] for row in matching})
        if transform == "90" and quarter_turn:
            assert "tiled" in paths, (name, "90-degree candidate path not observed", paths)
        if transform == "180":
            assert paths == ["sampler"], (name, "180-degree path should remain sampler", paths)
        result["draw_trace"] = {
            "rows": len(matching), "paths": paths,
            "tiled_rows": sum(row[0] == "tiled" for row in matching),
            "sampler_rows": sum(row[0] == "sampler" for row in matching),
            "max_copy_cpu_ns": max(row[1] for row in matching),
            "max_total_cpu_ns": max(row[2] for row in matching),
            "max_scratch_bytes": max(row[4] for row in matching),
        }
        result["evidence_class"] = "headless-qemu-real-compositor-changing-client"
        (runtime / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    finally:
        for process in reversed(children):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for stream in streams:
            stream.close()
        sway_log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sway", type=Path, required=True,
                        help="unwrapped candidate RISC-V Sway executable")
    parser.add_argument("--client", type=Path, required=True,
                        help="native animated Wayland client executable")
    parser.add_argument("--qemu", type=Path, default=Path("/usr/bin/qemu-riscv64-static"))
    parser.add_argument("--output", type=Path, required=True,
                        help="new or empty directory for machine-readable results and PNGs")
    args = parser.parse_args()
    for path, label in ((args.sway, "Sway"), (args.client, "client"), (args.qemu, "QEMU")):
        if not path.is_file() or not os.access(path, os.X_OK):
            parser.error(f"{label} executable not found or not executable: {path}")
    args.output = args.output.resolve()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("--output must be a new or empty directory")
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    runs = [
        ("turn90-sampler", "90", False),
        ("turn90-quarter-turn", "90", True),
        ("turn180-sampler-fallback", "180", True),
    ]
    report = {
        "result": "PASS",
        "evidence_class": "headless-qemu-real-compositor-changing-client",
        "physical_acceptance": "UNVERIFIED; no physical HDMI or touch interaction occurred",
        "artifacts": {
            "sway_path": str(args.sway.resolve()), "sway_sha256": digest(args.sway),
            "client_path": str(args.client.resolve()), "client_sha256": digest(args.client),
            "qemu_path": str(args.qemu.resolve()), "qemu_sha256": digest(args.qemu),
        },
        "runs": [],
    }
    for name, transform, enabled in runs:
        print(f"RUN {name}: transform={transform} quarter_turn={int(enabled)}", flush=True)
        report["runs"].append(run_variant(args, args.output, name, transform, enabled))
    (args.output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"result": report["result"], "output": str(args.output),
                      "runs": [{"name": run["name"], "rect": run["output"]["rect"],
                                "paths": run["draw_trace"]["paths"]}
                               for run in report["runs"]]}, indent=2))


if __name__ == "__main__":
    main()
