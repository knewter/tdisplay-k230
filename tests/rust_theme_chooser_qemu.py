#!/usr/bin/env python3
"""Paired Sway/Rust theme chooser touch proof with a synthetic theme command.

The fixture never calls the real theme transaction or modifies user themes.
Synthetic Wayland touch and headless screenshots are not physical panel proof.
"""

import argparse
from contextlib import closing, nullcontext
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import time

from PIL import Image, ImageChops


THEME_COMMAND = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ["K230_TEST_THEME_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
generation = "b" * 24
themes = [{"id": f"{i:024x}", "name": f"Fixture {i:02d}",
           "label": f"Fixture {i:02d}", "origin": "builtin"}
          for i in range(18)]
if args == ["list"]:
    answer = {"schema": 1, "themes": themes,
              "active": {"id": themes[0]["id"], "generation": generation}}
else:
    assert args[0] in ("preview", "activate") and args[1] in {row["id"] for row in themes}
    if args[0] == "activate":
        assert args[args.index("--expected-generation") + 1] == generation
    selected = args[args.index("--background") + 1] if "--background" in args else "c" * 24
    assert selected in ("c" * 24, "d" * 24)
    directory = Path(os.environ["K230_TEST_THEME_GENERATION"]) / generation
    answer = {"schema": 1, "theme": next(row for row in themes if row["id"] == args[1]),
              "generation": generation, "appearance_path": str(directory / "appearance.json"),
              "palette": {"background": "#101820", "foreground": "#f1f4f5",
                          "accent": "#69ccbc"}, "icon_theme": "hicolor",
              "backgrounds": [
                  {"id": "c" * 24, "label": "Fixture still one", "kind": "image",
                   "path": str(directory / "theme/backgrounds/one.png"),
                   "selected": selected == "c" * 24, "decode_status": "unverified"},
                  {"id": "d" * 24, "label": "Fixture still two", "kind": "image",
                   "path": str(directory / "theme/backgrounds/two.png"),
                   "selected": selected == "d" * 24, "decode_status": "unverified"},
              ],
              "compatibility": {"applied": ["launcher"], "unavailable": [], "unknown": []},
              "activated": args[0] == "activate"}
    if args[0] == "activate":
        answer["app_appearance"] = {"state": "applied", "generation": generation,
                                    "error": None, "kind": None}
print(json.dumps(answer))
'''


def wait_for(predicate, seconds=25):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.05)
    raise AssertionError("timed out waiting for theme chooser state")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sway", type=Path, required=True)
    parser.add_argument("--rust", type=Path, required=True)
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    parser.add_argument("--output", type=Path, help="keep synthetic images and logs")
    args = parser.parse_args()
    if not args.sway.is_file() or not args.rust.is_file():
        parser.error("exact cross-built Sway and Rust executables must exist")
    if args.output:
        args.output.mkdir(parents=True, exist_ok=False)
    context = nullcontext(args.output) if args.output else tempfile.TemporaryDirectory(prefix="k230-theme-ui-qemu-")
    with context as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        config = root / "sway.conf"
        config.write_text("output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n")
        command = root / "synthetic-k230-theme"
        command.write_text(THEME_COMMAND)
        command.chmod(0o700)
        log = root / "theme-commands.jsonl"
        log.touch()
        env = dict(os.environ, XDG_RUNTIME_DIR=str(root), WLR_BACKENDS="headless",
                   WLR_HEADLESS_OUTPUTS="1", WLR_RENDERER="pixman",
                   SWAY_K230_CARD_SHELL="1", SWAY_K230_CARD_TEST_INPUT="1",
                   K230_THEME_COMMAND=str(command), K230_TEST_THEME_LOG=str(log),
                   K230_TEST_THEME_GENERATION=str(root / "generations"))
        sway_log = (root / "sway.log").open("w")
        rust_log = (root / "rust.log").open("w")
        sway = subprocess.Popen([args.qemu, str(args.sway), "-c", str(config), "-d"],
                                env=env, stdout=sway_log, stderr=sway_log)
        rust = None
        try:
            wait_for(lambda: "Running compositor on wayland display" in (root / "sway.log").read_text(), 60)
            env["WAYLAND_DISPLAY"] = wait_for(lambda: next(
                (path.name for path in root.glob("wayland-*") if not path.name.endswith(".lock")), None))
            rust = subprocess.Popen([args.qemu, str(args.rust), "--serve"],
                                    env=env, stdout=rust_log, stderr=rust_log)
            wait_for(lambda: "ready-idle" in (root / "rust.log").read_text(), 30)

            def ipc(command_text):
                name = next(root.glob("sway-ipc.*.sock"))
                with closing(socket.socket(socket.AF_UNIX)) as stream:
                    stream.settimeout(10)
                    stream.connect(str(name))
                    payload = command_text.encode()
                    stream.sendall(b"i3-ipc" + struct.pack("=II", len(payload), 0) + payload)
                    def read(count):
                        data = b""
                        while len(data) < count:
                            chunk = stream.recv(count - len(data))
                            assert chunk, "Sway IPC closed"
                            data += chunk
                        return data
                    length, _ = struct.unpack("=II", read(14)[6:])
                    answer = json.loads(read(length))
                    assert all(row["success"] for row in answer), (command_text, answer)

            def calls():
                return [json.loads(line) for line in log.read_text().splitlines()]

            def commits():
                return sum(line.endswith(" commit") for line in (root / "rust.log").read_text().splitlines())

            def capture(name):
                path = root / name
                subprocess.run(["grim", str(path)], env=env, check=True)
                with Image.open(path) as image:
                    return image.convert("RGB")

            contact = 1
            def tap(x, y):
                nonlocal contact
                ipc(f"card_shell test-touch down {contact} {x} {y}")
                ipc(f"card_shell test-touch up {contact}")
                contact += 1

            def swipe(x, y1, y2):
                nonlocal contact
                ipc(f"card_shell test-touch down {contact} {x} {y1}")
                ipc(f"card_shell test-touch motion {contact} {x} {y2}")
                ipc(f"card_shell test-touch up {contact}")
                contact += 1

            ipc("card_shell test-touch init")
            subprocess.run([args.qemu, str(args.rust), "--surface", "settings"],
                           env=env, check=True, stdout=subprocess.DEVNULL)
            wait_for(lambda: commits() >= 1)
            controls = capture("settings.png")
            before = commits()
            tap(475, 130)
            wait_for(lambda: calls() == [["list"]])
            wait_for(lambda: commits() >= before + 2)
            listing = capture("theme-list.png")
            assert ImageChops.difference(controls, listing).getbbox(), "chooser list was not painted"
            before = commits()
            swipe(300, 850, 550)
            wait_for(lambda: commits() > before)
            scrolled = capture("theme-list-scrolled.png")
            assert ImageChops.difference(listing.crop((20, 204, 548, 1100)),
                                         scrolled.crop((20, 204, 548, 1100))).getbbox(), \
                "touch scroll did not move theme rows"
            assert all(row[0] != "activate" for row in calls())
            before = commits()
            tap(280, 240)
            wait_for(lambda: any(row[0] == "preview" for row in calls()))
            wait_for(lambda: commits() >= before + 2)
            preview = capture("theme-preview.png")
            assert ImageChops.difference(scrolled, preview).getbbox(), "preview was not painted"
            assert all(row[0] != "activate" for row in calls())
            selected_theme = [row for row in calls() if row[0] == "preview"][-1][1]
            before = commits()
            tap(280, 780)  # Choose the second still, rather than the default first.
            wait_for(lambda: any(row[:2] == ["preview", selected_theme] and "--background" in row
                                 for row in calls()), 20)
            wait_for(lambda: commits() >= before + 2)
            selected = capture("theme-background-selected.png")
            assert ImageChops.difference(preview, selected).getbbox(), \
                "background selection did not update preview"
            assert all(row[0] != "activate" for row in calls())
            before = commits()
            tap(120, 1150)  # Cancel preview; return to list without activation.
            wait_for(lambda: calls()[-1] == ["list"])
            wait_for(lambda: commits() >= before + 2)
            assert all(row[0] != "activate" for row in calls())
            before = commits()
            tap(280, 240)
            wait_for(lambda: calls()[-1][0] == "preview")
            wait_for(lambda: commits() >= before + 2)
            tap(440, 1150)  # Only this explicit Apply may activate.
            wait_for(lambda: any(row[0] == "activate" for row in calls()))
            activation = [row for row in calls() if row[0] == "activate"]
            assert len(activation) == 1 and "--expected-generation" in activation[0]
            assert activation[0][activation[0].index("--expected-generation") + 1] == "b" * 24
            print("PASS paired Sway/Rust theme chooser QEMU touch, synthetic backend; no physical touch")
        finally:
            if rust is not None:
                rust.terminate()
                try: rust.wait(timeout=5)
                except subprocess.TimeoutExpired: rust.kill(); rust.wait(timeout=5)
            sway.terminate()
            try: sway.wait(timeout=5)
            except subprocess.TimeoutExpired: sway.kill(); sway.wait(timeout=5)
            rust_log.close()
            sway_log.close()


if __name__ == "__main__":
    main()
