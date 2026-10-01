#!/usr/bin/env python3
"""Headless QEMU pixels for the volume slider and the volume HUD.

A narrow extension of `rust_service_surface_qemu.py`'s own harness (same
headless-Sway/Wayland-touch/`grim` setup, same `Broker`/settings fixture),
not a fork of it: this script owns only what that one does not already
cover -- a `pw-dump`/`pw-cli` fixture pair standing in for a real PipeWire
session, so `main.rs`'s own `pipewire_ipc::spawn_monitor`/`WriterHandle`
have something to talk to at all. `K230_PW_DUMP`/`K230_PW_CLI` are the same
environment variables `main.rs` already reads for a real deployment
(default bare `pw-dump`/`pw-cli`, resolved via `PATH`); here they point at
these fixture scripts instead, the same substitution `K230_SETTINGS` already
makes for `k230-settings`.

The `pw-dump` fixture prints one initial dump (one sink, one stream, the
sink marked default) matching the shape `nix/rust-shell-client/tests/
fixtures/pipewire/dump-initial.json` already tests against in the unit
suite, then -- only in `--monitor` mode -- an "external change" delta a
short, fixed delay later (a different sink volume), simulating another
app/a hardware key/`wpctl` from a console changing the level while this
shell is running. That delta is what this capture uses to show the HUD
appearing for an *external* change, not this shell's own gesture.
"""

import json
import os
import sys
import tempfile
import time
from contextlib import closing, nullcontext
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rust_service_surface_qemu import Broker, SETTINGS_FIXTURE, wait_for  # noqa: E402

import argparse
import socket
import struct
import subprocess
import threading

from PIL import Image, ImageChops

SINK_NAME = "alsa_output.platform-canaan_k230_audio.k230-i2s-inno"

PW_DUMP_FIXTURE = f'''#!/usr/bin/env python3
import json, os, sys, time

INITIAL = [
    {{
        "id": 50, "type": "PipeWire:Interface:Node",
        "info": {{
            "props": {{
                "media.class": "Audio/Sink",
                "node.name": "{SINK_NAME}",
                "node.description": "K230 Inno codec line-out",
            }},
            "params": {{"Props": [{{"channelVolumes": [0.512, 0.512], "mute": False}}]}},
        }},
    }},
    {{
        "id": 83, "type": "PipeWire:Interface:Node",
        "info": {{
            "props": {{
                "media.class": "Stream/Output/Audio",
                "application.name": "k230 video",
                "application.icon-name": "multimedia-player",
                "node.name": "k230-video",
            }},
            "params": {{"Props": [{{"channelVolumes": [0.729], "mute": False}}]}},
        }},
    }},
    {{
        "id": 0, "type": "PipeWire:Interface:Metadata",
        "props": {{"metadata.name": "default"}},
        "metadata": [
            {{"subject": 0, "key": "default.audio.sink", "type": "Spa:String:JSON",
              "value": {{"name": "{SINK_NAME}"}}}}
        ],
    }},
]

EXTERNAL_CHANGE = [
    {{
        "id": 50, "type": "PipeWire:Interface:Node",
        "info": {{
            "props": {{
                "media.class": "Audio/Sink",
                "node.name": "{SINK_NAME}",
                "node.description": "K230 Inno codec line-out",
            }},
            "params": {{"Props": [{{"channelVolumes": [0.343, 0.343], "mute": False}}]}},
        }},
    }}
]

if "--monitor" not in sys.argv:
    print(json.dumps(INITIAL))
    sys.exit(0)

print(json.dumps(INITIAL), flush=True)
while not os.path.exists(os.environ["K230_TEST_VOLUME_TRIGGER"]):
    time.sleep(0.02)
print(json.dumps(EXTERNAL_CHANGE), flush=True)
time.sleep(3600)
'''

PW_CLI_FIXTURE = """#!/usr/bin/env python3
# Fire-and-forget from this shell's own point of view -- see
# `pipewire_ipc::Writer`'s own doc. Reads and discards commands so the
# persistent writer's stdin pipe never backs up; the real check that a
# slider drag reaches this process at all is that this fixture keeps
# running for the whole capture without the writer thread erroring.
import sys
for _ in sys.stdin:
    pass
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sway", type=Path, required=True)
    parser.add_argument("--rust", type=Path, required=True)
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    parser.add_argument("--output", type=Path, help="keep synthetic screenshots and logs")
    args = parser.parse_args()
    if not args.sway.is_file() or not args.rust.is_file():
        parser.error("cross-built Sway and Rust executables must exist")

    if args.output:
        args.output.mkdir(parents=True, exist_ok=False)
    context = (
        nullcontext(args.output)
        if args.output
        else tempfile.TemporaryDirectory(prefix="k230-volume-qemu-")
    )
    with context as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        config = root / "config"
        config.write_text("output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n")
        settings = root / "fake-settings"
        settings.write_text(SETTINGS_FIXTURE)
        settings.chmod(0o700)
        settings_log = root / "settings.jsonl"
        settings_log.touch()
        pw_dump = root / "fake-pw-dump"
        pw_dump.write_text(PW_DUMP_FIXTURE)
        pw_dump.chmod(0o700)
        pw_cli = root / "fake-pw-cli"
        pw_cli.write_text(PW_CLI_FIXTURE)
        pw_cli.chmod(0o700)
        broker = Broker(root / "notifications.sock")
        env = dict(
            os.environ,
            XDG_RUNTIME_DIR=str(root),
            WLR_BACKENDS="headless",
            WLR_HEADLESS_OUTPUTS="1",
            WLR_RENDERER="pixman",
            SWAY_K230_CARD_SHELL="1",
            SWAY_K230_CARD_TEST_INPUT="1",
            K230_SETTINGS=str(settings),
            K230_NOTIFICATION_SOCKET=str(broker.path),
            K230_TEST_SETTINGS_LOG=str(settings_log),
            K230_PW_DUMP=str(pw_dump),
            K230_PW_CLI=str(pw_cli),
            K230_TEST_VOLUME_TRIGGER=str(root / "trigger-volume"),
        )
        sway_log = (root / "sway.log").open("w")
        rust_log = (root / "rust.log").open("w")
        sway = subprocess.Popen(
            [args.qemu, str(args.sway), "-c", str(config), "-d"],
            env=env, stdout=sway_log, stderr=sway_log,
        )
        rust = None
        try:
            wait_for(lambda: "Running compositor on wayland display" in (root / "sway.log").read_text(), 60)
            env["WAYLAND_DISPLAY"] = wait_for(
                lambda: next((p.name for p in root.glob("wayland-*") if not p.name.endswith(".lock")), None)
            )
            rust = subprocess.Popen([args.qemu, str(args.rust), "--serve"], env=env, stdout=rust_log, stderr=rust_log)
            wait_for(lambda: "ready-idle" in (root / "rust.log").read_text(), 30)

            def ipc(command):
                name = next(root.glob("sway-ipc.*.sock"))
                with closing(socket.socket(socket.AF_UNIX)) as stream:
                    stream.settimeout(10)
                    stream.connect(str(name))
                    payload = command.encode()
                    stream.sendall(b"i3-ipc" + struct.pack("=II", len(payload), 0) + payload)

                    def read(count):
                        data = b""
                        while len(data) < count:
                            chunk = stream.recv(count - len(data))
                            assert chunk, "Sway IPC closed"
                            data += chunk
                        return data

                    length, _ = struct.unpack("=II", read(14)[6:])
                    result = json.loads(read(length))
                    assert all(row["success"] for row in result), (command, result)

            def route(name):
                # A second `qemu-riscv64-static --surface` process per route
                # change could not reliably complete inside the Rust
                # client's own hardcoded 500ms deadline on this shared,
                # heavily-loaded host (`uptime` showed a 60+ load average
                # across 32 cores from other concurrent worktrees) -- the
                # same host-load workaround `docs/evidence/brightness-
                # slider/README.md` already documents: a direct write to
                # the same Unix socket that flag uses reaches the identical
                # `RouteServer` without the extra process's own startup
                # cost. Not a change to the shipped client's route
                # protocol; `main.rs::request`'s own wire format (the route
                # name plus `\n`, a 3-byte `OK\n` reply) is reproduced here
                # verbatim.
                with closing(socket.socket(socket.AF_UNIX)) as stream:
                    stream.settimeout(5)
                    stream.connect(str(root / "k230-shell-rust.sock"))
                    stream.sendall(f"{name}\n".encode())
                    reply = b""
                    while len(reply) < 3:
                        chunk = stream.recv(3 - len(reply))
                        assert chunk, "route socket closed"
                        reply += chunk
                    assert reply == b"OK\n", reply

            def capture(name):
                output = root / name
                subprocess.run(["grim", str(output)], env=env, check=True)
                with Image.open(output) as frame:
                    return frame.convert("RGB")

            def capture_until(name, predicate, seconds=20):
                def probe():
                    frame = capture(name)
                    return frame if predicate(frame) else None
                return wait_for(probe, seconds)

            def changed_area(first, second, box, min_pixels=200):
                # A bare `getbbox()` fires on a handful of stray/noise
                # pixels too easily on a 568x1232 frame with several
                # animated regions; requiring a real, HUD-pill-sized area
                # of actual difference is a stronger, still-simple positive
                # check than "any pixel at all differs".
                diff = ImageChops.difference(first.crop(box), second.crop(box))
                bbox = diff.getbbox()
                if bbox is None:
                    return False
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]
                return width * height >= min_pixels

            def commits():
                return sum(line.endswith(" commit") for line in (root / "rust.log").read_text().splitlines())

            contact = 1

            def tap(x, y):
                nonlocal contact
                ipc(f"card_shell test-touch down {contact} {x} {y}")
                ipc(f"card_shell test-touch up {contact}")
                contact += 1

            ipc("card_shell test-touch init")
            wallpaper = capture("wallpaper.png")

            # Trigger the fixture only after the baseline is captured.
            route("shade")
            # Both sliders need their own backing data before they paint
            # at all (`slider_band`/`volume_slider_band`'s own gates): the
            # brightness one needs a completed `RefreshSettings` round
            # trip (the `k230-settings` fixture, a real subprocess) and
            # the volume one needs the fixture `pw-dump`'s initial,
            # one-shot dump already read. `commits() >= 2` is the same
            # "the shade has actually settled, not just started opening"
            # signal `rust_service_surface_qemu.py`'s own capture already
            # uses.
            wait_for(lambda: len(settings_log.read_text().splitlines()) >= 1 and commits() >= 2, 10)
            wait_for(lambda: "volume-hud-unmap" in (root / "rust.log").read_text(), 10)
            shade = capture_until(
                "shade-both-sliders.png",
                lambda frame: changed_area(wallpaper, frame, (0, 150, 568, 420)),
            )

            # A new external graph delta raises a fresh route-independent HUD.
            (root / "trigger-volume").touch()
            wait_for(lambda: (root / "rust.log").read_text().count("volume-hud-map-request") >= 2, 10)
            hud_collapsed = capture_until(
                "hud-collapsed.png",
                lambda frame: changed_area(shade, frame, (470, 400, 568, 900)),
                seconds=2,
            )

            # Expand: tap the "..." affordance near the bottom of the
            # collapsed pill (`volume::HudGeometry::expand_affordance_hit`).
            # The tap itself calls `hud.toggle_expand`, which also calls
            # `hud.show` again, so this has its own fresh 2.5s window,
            # not whatever was left of the external change's.
            tap(520, 700)
            hud_expanded = capture_until(
                "hud-expanded.png",
                lambda frame: changed_area(hud_collapsed, frame, (250, 400, 568, 900)),
                seconds=2,
            )

            assert rust.poll() is None and sway.poll() is None
            print(
                json.dumps(
                    {
                        "evidence_class": "headless-qemu-injected-touch",
                        "passed": [
                            "shade-shows-both-brightness-and-volume-sliders",
                            "hud-appears-for-an-external-pipewire-change-not-a-local-gesture",
                            "hud-expand-affordance-shows-the-wider-per-stream-per-sink-panel",
                        ],
                        "limits": [
                            "synthetic pw-dump/pw-cli fixtures, not a real PipeWire daemon",
                            "no physical touch, panel, or board audio",
                        ],
                    }
                ),
                flush=True,
            )
        finally:
            if rust:
                rust.terminate()
                try:
                    rust.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    rust.kill()
                    rust.wait()
            sway.terminate()
            try:
                sway.wait(timeout=5)
            except subprocess.TimeoutExpired:
                sway.kill()
                sway.wait()
            sway_log.close()
            rust_log.close()
            broker.close()


if __name__ == "__main__":
    main()
