#!/usr/bin/env python3
"""Paired Sway/Rust notification-motion pixels with invented broker events.

Run on a host with qemu-riscv64-static, grim and Pillow. The compositor's
headless test-touch route supplies contact; no board, radio or private app is
opened. A fixed local broker records only operation names and numeric IDs.
"""

import argparse
from contextlib import closing, nullcontext
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time

from PIL import Image, ImageChops


def wait_for(predicate, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.04)
    raise AssertionError("timed out waiting for synthetic notification motion")


class Broker:
    def __init__(self, path):
        self.path = path
        self.events = [self.event(index) for index in range(1, 13)]
        self.operations = []
        self.lock = threading.Lock()
        self.listener = socket.socket(socket.AF_UNIX)
        self.listener.bind(str(path))
        path.chmod(0o600)
        self.listener.listen(8)
        self.listener.settimeout(0.2)
        self.stop = False
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    @staticmethod
    def event(index):
        critical = index == 1
        return {"id": index, "source": "Fixture", "icon": None,
                "summary": f"Synthetic event {index}", "body": "Public test content",
                "priority": "critical" if critical else "ordinary",
                "timestamp": 1700000000 + index, "error": None,
                "dismissible": not critical, "action_available": index == 2}

    def count(self, operation):
        with self.lock:
            return sum(name == operation for name, _ in self.operations)

    def run(self):
        while not self.stop:
            try:
                connection, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with connection:
                connection.settimeout(3)
                try:
                    line = bytearray()
                    while len(line) < 4096 and not line.endswith(b"\n"):
                        chunk = connection.recv(4096 - len(line))
                        if not chunk:
                            break
                        line.extend(chunk)
                    request = json.loads(line)
                    operation = request["operation"]
                    event_id = request.get("id")
                    with self.lock:
                        self.operations.append((operation, event_id))
                        if operation == "history":
                            answer = {"schema": 1, "count": len(self.events),
                                      "events": list(self.events), "preview": None}
                        elif operation == "dismiss" and event_id != 1:
                            self.events = [row for row in self.events if row["id"] != event_id]
                            answer = {"state": "dismissed"}
                        else:
                            answer = {"state": "failed", "error": "fixture-rejected"}
                    if operation == "dismiss":
                        # Keep the old row visible while the response is in
                        # flight, so a tap at its old slot tests action gating.
                        time.sleep(0.3)
                    connection.sendall(json.dumps(answer).encode() + b"\n")
                except (OSError, ValueError, KeyError):
                    # Do not echo a request or its content into test output.
                    pass

    def close(self):
        self.stop = True
        self.listener.close()
        self.thread.join(timeout=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sway", type=Path, required=True)
    parser.add_argument("--rust", type=Path, required=True)
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.sway.is_file() or not args.rust.is_file():
        parser.error("exact cross-built Sway and Rust executables must exist")
    if args.output:
        args.output.mkdir(parents=True, exist_ok=False)
    context = nullcontext(args.output) if args.output else tempfile.TemporaryDirectory(prefix="k230-notification-qemu-")
    with context as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        (root / "sway.conf").write_text("output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n")
        broker = Broker(root / "notifications.sock")
        env = dict(os.environ, XDG_RUNTIME_DIR=str(root), WLR_BACKENDS="headless",
                   WLR_HEADLESS_OUTPUTS="1", WLR_RENDERER="pixman",
                   SWAY_K230_CARD_SHELL="1", SWAY_K230_CARD_TEST_INPUT="1",
                   K230_SETTINGS="/bin/false", K230_NOTIFICATION_SOCKET=str(broker.path))
        sway_log = (root / "sway.log").open("w")
        sway = subprocess.Popen([args.qemu, str(args.sway), "-c", str(root / "sway.conf"), "-d"],
                                env=env, stdout=sway_log, stderr=sway_log)
        rust = None
        rust_log = None
        try:
            wait_for(lambda: "Running compositor on wayland display" in (root / "sway.log").read_text(), 60)
            env["WAYLAND_DISPLAY"] = wait_for(lambda: next(
                (path.name for path in root.glob("wayland-*") if not path.name.endswith(".lock")), None))

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
                            chunk = stream.recv(count-len(data))
                            assert chunk
                            data += chunk
                        return data
                    length, _ = struct.unpack("=II", read(14)[6:])
                    assert all(row["success"] for row in json.loads(read(length)))

            def route(name):
                subprocess.run([args.qemu, str(args.rust), "--surface", name],
                               env=env, check=True, stdout=subprocess.DEVNULL)

            def capture(name):
                path = root / name
                subprocess.run(["grim", str(path)], env=env, check=True)
                with Image.open(path) as frame:
                    return frame.convert("RGB")

            video_counts = {"swipe-return": 0, "scroll-stop": 0}
            frames_dir = root / "_video_frames"
            if args.output:
                frames_dir.mkdir()

            def video_frame(phase):
                if args.output:
                    number = video_counts[phase]
                    video_counts[phase] += 1
                    capture(f"_video_frames/{phase}-{number:03d}.png")

            def encode_videos():
                if not args.output:
                    return
                for phase, count in video_counts.items():
                    assert count >= 6, (phase, count)
                    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
                                    "-framerate", "12", "-i",
                                    str(frames_dir / f"{phase}-%03d.png"),
                                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                                    str(root / f"{phase}.mp4")], check=True)
                shutil.rmtree(frames_dir)

            def changed(first, second, region=(24, 266, 544, 765)):
                return ImageChops.difference(first.crop(region), second.crop(region)).getbbox() is not None

            def capture_until(name, predicate):
                return wait_for(lambda: (frame if predicate(frame) else None)
                                if (frame := capture(name)) else None)

            def launch():
                nonlocal rust, rust_log
                rust_log = (root / "rust.log").open("w")
                rust = subprocess.Popen([args.qemu, str(args.rust), "--serve"],
                                        env=env, stdout=rust_log, stderr=rust_log)
                wait_for(lambda: "ready-idle" in (root / "rust.log").read_text() and rust.poll() is None, 30)
                route("shade")
                wait_for(lambda: broker.count("history") >= 1)
                # The broker can answer before the replacement layer has
                # attached its first buffer; wait for pixels, not IPC alone.
                wait_for(lambda: (frame := capture("ready.png")).getpixel((28, 300))
                         != frame.getpixel((10, 300)))

            def stop_client():
                nonlocal rust, rust_log
                rust.terminate(); rust.wait(timeout=5); rust = None
                rust_log.close(); rust_log = None

            contact = 1
            def down(x, y):
                nonlocal contact
                ipc(f"card_shell test-touch down {contact} {x} {y}")
            def motion(x, y):
                ipc(f"card_shell test-touch motion {contact} {x} {y}")
            def up():
                nonlocal contact
                ipc(f"card_shell test-touch up {contact}")
                contact += 1

            ipc("card_shell test-touch init")
            launch()
            initial = capture_until("initial.png", lambda frame: frame.getpixel((28, 300)) != frame.getpixel((10, 300)))
            # Critical first row must remain fixed and cannot dismiss.
            down(300, 315); motion(445, 315)
            critical_held = capture("critical-held.png")
            assert not changed(initial, critical_held, (24, 266, 544, 374))
            up()
            time.sleep(0.25)
            assert broker.count("dismiss") == 0

            # A short/reversed horizontal drag must animate back from visible pixels.
            down(300, 420); video_frame("swipe-return")
            motion(350, 420); video_frame("swipe-return")
            motion(420, 420)
            held = capture_until("swipe-held.png", lambda frame: changed(initial, frame, (24, 382, 544, 490)))
            video_frame("swipe-return")
            motion(326, 420)
            reversed_frame = capture_until("swipe-reversed.png", lambda frame: changed(held, frame, (24, 382, 544, 490)))
            video_frame("swipe-return")
            up()
            early = capture("swipe-return-early.png")
            video_frame("swipe-return")
            assert changed(initial, reversed_frame, (24, 382, 544, 490))
            assert changed(initial, early, (24, 382, 544, 490)), "release snapped directly to rest"
            for _ in range(6):
                time.sleep(0.025)
                video_frame("swipe-return")
            wait_for(lambda: not changed(initial, capture("swipe-return-rest.png"), (24, 382, 544, 490)))
            video_frame("swipe-return")
            assert broker.count("dismiss") == 0

            # Once vertical deviation cancels a row swipe, its return may
            # animate while that same touch remains down; release cannot fire.
            down(300, 420); motion(420, 420)
            capture_until("swipe-vertical-held.png",
                          lambda frame: changed(initial, frame, (24, 382, 544, 490)))
            motion(420, 510)
            capture_until("swipe-vertical-cancel.png",
                          lambda frame: not changed(initial, frame, (24, 382, 544, 490)))
            up()
            assert broker.count("dismiss") == 0

            # Finger-tracked list drag, bounded coast and tap-to-stop.
            down(300, 630); video_frame("scroll-stop")
            time.sleep(0.06); motion(300, 555)
            held_scroll = capture_until("scroll-held.png", lambda frame: changed(initial, frame))
            video_frame("scroll-stop")
            # Frame capture can exceed the 120ms release-velocity freshness
            # bound in QEMU. Refresh the sample, then release immediately.
            motion(300, 570)
            time.sleep(0.04); motion(300, 490)
            up()
            coast = capture_until("scroll-coasting.png", lambda frame: changed(held_scroll, frame))
            video_frame("scroll-stop")
            # A second changed frame after release rules out merely seeing
            # the last delayed held-contact repaint.
            coast_next = capture_until("scroll-coasting-next.png",
                                       lambda frame: changed(coast, frame))
            assert changed(coast, coast_next)
            video_frame("scroll-stop")
            down(300, 540); up()  # stop without opening a history action
            # Under emulation a pre-tap buffer can sit behind two frame-done
            # callbacks; compare after that queue drains, not its old pixels.
            time.sleep(0.45)
            stopped = capture("scroll-stopped.png")
            video_frame("scroll-stop")
            for _ in range(3):
                time.sleep(0.025)
                video_frame("scroll-stop")
            time.sleep(0.18)
            stable = capture("scroll-stable.png")
            video_frame("scroll-stop")
            assert not changed(stopped, stable), "history drifted after tap-to-stop"
            assert broker.count("action") == 0

            # Reset list position via a fresh client, then complete one row dismissal.
            stop_client(); launch()
            before = capture("dismiss-before.png")
            history_before = broker.count("history")
            down(300, 420); motion(445, 420); up()
            assert broker.count("dismiss") == 0, "broker request preceded exit motion"
            wait_for(lambda: broker.count("dismiss") == 1)
            down(300, 420); up()  # old hitbox must not activate the pending event
            wait_for(lambda: broker.count("history") > history_before)
            # Do not mistake the exit frame for the broker's settled reply.
            # Event 3 must occupy event 2's old slot with identical pixels.
            old_third = before.crop((24, 498, 544, 606))
            after = capture_until("dismiss-after.png", lambda frame:
                                  ImageChops.difference(old_third,
                                      frame.crop((24, 382, 544, 490)))
                                  .point(lambda channel: 0 if channel <= 3 else 255)
                                  .getbbox() is None)
            assert changed(before, after, (24, 382, 544, 490))
            with broker.lock:
                assert len(broker.events) == 11 and broker.events[0]["id"] == 1
            assert broker.count("action") == 0, "pending dismiss leaked an old-row action"
            assert rust.poll() is None and sway.poll() is None
            encode_videos()
            print(json.dumps({"evidence_class": "headless-qemu-injected-touch",
                              "passed": ["critical-fixed", "swipe-reverse-settle",
                                         "swipe-vertical-cancel",
                                         "history-coast", "tap-stop", "release-after-exit-dismiss",
                                         "pending-dismiss-no-action"],
                              "limits": ["invented broker/events", "no physical glass or frame timing"]}), flush=True)
        finally:
            if rust:
                rust.terminate()
                try: rust.wait(timeout=5)
                except subprocess.TimeoutExpired: rust.kill(); rust.wait()
            sway.terminate()
            try: sway.wait(timeout=5)
            except subprocess.TimeoutExpired: sway.kill(); sway.wait()
            if rust_log: rust_log.close()
            sway_log.close()
            broker.close()


if __name__ == "__main__":
    main()
