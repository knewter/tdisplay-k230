#!/usr/bin/env python3
"""Headless QEMU proof of the instant launch splash and its hand-off.

Synthetic touch and a private desktop catalog; never physical panel evidence.
This proves wiring/timing under QEMU's headless Pixman backend with a real
mapped fixture window, not real-glass splash readability, touch-dismiss feel,
or that the previously active app is imperceptible on the physical panel --
see `openspec/changes/launching-an-app-shows-a-splash/tasks.md`'s board
acceptance tasks for what remains open.

The one catalog entry's `Exec` is a plain shell wrapper that sleeps briefly
then `exec`s the same native `card-composition-probe-client` fixture used by
`tests/card_shell_runtime.py`, under a fresh `--app-id`. `exec` (not a fork)
keeps the pid identical from the process GIO's `AppLaunchContext` reports
through to the process that actually owns the mapped Wayland window, so this
proves the exact-pid match path end to end; the bounded `/proc`-ancestry and
`Terminal=true`/`foot` app_id-mismatch paths are covered by
`splash::pid_or_ancestor`'s and `main.rs`'s own host unit tests, not
repeated here.
"""
import argparse
import json
import os
import pathlib
import socket
import struct
import subprocess
import time

from PIL import Image, ImageChops

parser = argparse.ArgumentParser(description=__doc__)
for field in ("sway", "swaymsg", "rust", "client", "output"):
    parser.add_argument("--" + field, required=True)
parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
args = parser.parse_args()
out = pathlib.Path(args.output)
out.mkdir(mode=0o700, exist_ok=False)
qemu = args.qemu
sway = args.sway
swaymsg = args.swaymsg
rust = args.rust
client = args.client

config = out / "sway.conf"
config.write_text(
    "output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n"
    "focus_follows_mouse no\n"
    'for_window [app_id="^k230.card."] floating enable, border none, '
    "resize set 520 1040, move position 24 48\n"
)
swaymsg_wrapper = out / "swaymsg"
swaymsg_wrapper.write_text(f'#!/bin/sh\nexec {qemu} {swaymsg} "$@"\n')
swaymsg_wrapper.chmod(0o700)

apps = out / "data/applications"
apps.mkdir(parents=True)
# A shell wrapper, not the native binary directly in `Exec=`: this must run
# from inside the already-`qemu-riscv64-static`-emulated Rust client exactly
# like the existing `swaymsg` wrapper does (a script's shebang hands off to
# the host's real `/bin/sh` transparently; that process then `exec`s back
# into emulation for the target riscv64 binary -- see this file's own
# module doc for why `exec`, not a fork, matters here).
fixture_launch = out / "launch-splash-fixture"
fixture_launch.write_text(
    "#!/bin/sh\nsleep 1\n"
    f'exec {qemu} {client} --app-id k230.card.two\n'
)
fixture_launch.chmod(0o700)
(apps / "k230-splash-fixture.desktop").write_text(
    "[Desktop Entry]\nType=Application\nName=Splash Fixture\n"
    f"Exec={fixture_launch}\n"
)

env = dict(
    os.environ,
    XDG_RUNTIME_DIR=str(out),
    XDG_DATA_HOME=str(out / "data"),
    XDG_DATA_DIRS=str(out / "data"),
    WLR_BACKENDS="headless",
    WLR_HEADLESS_OUTPUTS="1",
    WLR_RENDERER="pixman",
    SWAY_K230_CARD_SHELL="1",
    SWAY_K230_CARD_TOUCH_FIRST="1",
    SWAY_K230_CARD_TEST_INPUT="1",
    SWAY_K230_CARD_REVEAL_STREAM="1",
    SWAY_K230_CARD_SURFACE_SOCKET=str(out / "k230-shell-rust.sock"),
    K230_SWAYMSG=str(swaymsg_wrapper),
)
logs = {}
processes = []


def spawn(name, argv):
    log = (out / (name + ".log")).open("w")
    logs[name] = log
    process = subprocess.Popen(argv, env=env, stdout=log, stderr=log)
    processes.append(process)
    return process


def text(name):
    return (out / (name + ".log")).read_text()


def wait(predicate, seconds=20):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("timeout waiting for launch-splash QEMU state")


def ipc(command, kind=0):
    with socket.socket(socket.AF_UNIX) as stream:
        stream.settimeout(5)
        stream.connect(str(next(out.glob("sway-ipc.*.sock"))))
        payload = command.encode()
        stream.sendall(b"i3-ipc" + struct.pack("=II", len(payload), kind) + payload)

        def read(count):
            data = b""
            while len(data) < count:
                chunk = stream.recv(count - len(data))
                assert chunk, "Sway IPC closed"
                data += chunk
            return data

        length, _ = struct.unpack("=II", read(14)[6:])
        result = json.loads(read(length))
        if kind == 0:
            assert all(row["success"] for row in result), (command, result)
        return result


def touch(action):
    return ipc("card_shell test-touch " + action)


def capture(name):
    subprocess.run(["grim", str(out / name)], env=env, check=True)
    return Image.open(out / name).convert("RGB")


def tree_nodes(tree):
    yield tree
    for node in tree.get("nodes", []) + tree.get("floating_nodes", []):
        yield from tree_nodes(node)


def focused_app_id():
    return next((n.get("app_id") for n in tree_nodes(ipc("", 4)) if n.get("focused")), None)


_contact_counter = [1]


def tap_until_seen(x, y, marker, attempts=15, settle=0.4):
    """Injects a fresh tap at (x, y) repeatedly until `marker` shows up in the
    Rust log, retrying with a new contact id each time. A single injected
    touch can arrive slightly before the compositor actually marks this
    client's overlay input-ready (its own reveal-settle animation has not
    quite finished at 8-16ms poll granularity under emulation), and such a
    touch is simply dropped rather than queued -- so this retries the tap
    itself, not just the wait, which is the only thing that reliably closes
    that race under a headless-QEMU harness this slow."""
    for _ in range(attempts):
        _contact_counter[0] += 1
        contact = _contact_counter[0]
        touch(f"down {contact} {x} {y}")
        end = time.monotonic() + settle
        seen = False
        while time.monotonic() < end:
            if marker in text("rust"):
                seen = True
                break
            time.sleep(0.05)
        touch(f"up {contact}")
        if seen:
            return contact
        time.sleep(0.1)
    raise AssertionError(f"never observed {marker!r} after {attempts} tap attempts at ({x},{y})")


try:
    spawn("sway", [qemu, sway, "-c", str(config), "-d"])
    wait(lambda: "Running compositor on wayland display" in text("sway"), 60)
    env["WAYLAND_DISPLAY"] = next(p.name for p in out.glob("wayland-*") if not p.name.endswith(".lock"))
    env["SWAYSOCK"] = str(next(out.glob("sway-ipc.*.sock")))
    spawn("rust", [qemu, rust, "--serve"])
    wait(lambda: "ready-idle" in text("rust"))
    spawn("client", [client, "--app-id", "k230.card.one"])
    wait(lambda: "k230.card.one" in json.dumps(ipc("", 4)))
    ipc("card_shell test-touch init")
    ipc("card_shell enter")
    wait(lambda: "K230_CARD_SHELL mirror id=" in text("sway"))
    deck = capture("deck.png")

    # Open the drawer -- the same upward swipe every other Rust-client QEMU
    # test uses.
    touch("down 1 284 1200")
    touch("motion 1 284 400")
    touch("up 1")
    wait(lambda: "map-request" in text("rust") and text("rust").count("commit") >= 2)
    time.sleep(1.0)
    opened = capture("drawer-open.png")
    assert ImageChops.difference(deck, opened).getbbox(), "drawer must visibly open over the deck"

    # The single catalog entry sits at the drawer grid's first tile
    # (navigation.rs: COLUMNS=3, list_top(1232)=415.08, TILE_HEIGHT=148 ->
    # tile 0 spans roughly x in [24,189], y in [415,563]).
    tap_until_seen(100, 480, "touch-down")

    # The splash must appear immediately, on the *same* overlay: no `unmap`
    # at all yet -- that is the flash this feature removes. `app-launch-
    # requested` confirms GIO's own launch (and pid capture) succeeded.
    wait(lambda: "app-launch-requested" in text("rust") or "app-launch-failed" in text("rust"), 8)
    assert "app-launch-requested" in text("rust"), text("rust")[-2000:]
    assert text("rust").count("unmap") == 0, "the overlay must never unmap before hand-off"
    time.sleep(0.2)
    splash = capture("splash.png")
    assert ImageChops.difference(opened, splash).getbbox(), (
        "the splash must visibly replace the drawer within one frame of the tap"
    )
    assert "splash-render-failed" not in text("rust")
    assert "splash-bake-failed" not in text("rust")

    # The fixture's own `sleep 1` means the splash is still `Pending` here,
    # well before the fixture's window can possibly have mapped -- proving
    # the splash actually stays up rather than being a one-frame flash of
    # its own.
    assert "app-launch-mapped" not in text("rust")

    # Now wait for the fixture's real window to map and this client's own
    # pid-matched hand-off to fire.
    wait(lambda: "k230.card.two" in json.dumps(ipc("", 4)), 15)
    wait(lambda: "app-launch-mapped" in text("rust"), 15)
    wait(lambda: text("rust").count("unmap") >= 1, 5)
    time.sleep(0.2)
    handoff = capture("handoff.png")
    assert ImageChops.difference(splash, handoff).getbbox(), "hand-off must visibly remove the splash"
    assert focused_app_id() == "k230.card.two", "the launched window must end up focused"

    result = {
        "result": "PASS",
        "class": "headless-qemu-native-touch",
        "splash_replaced_drawer": True,
        "no_unmap_before_handoff": True,
        "handoff_focused_app_id": "k230.card.two",
        "sway": sway,
        "rust": rust,
        "client": client,
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
finally:
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
    for log in logs.values():
        log.close()
