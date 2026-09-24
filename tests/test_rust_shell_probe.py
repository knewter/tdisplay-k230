"""Focused host checks for the opt-in Rust Wayland shell probe.

No case in this file opens a Wayland compositor or proves panel presentation.
"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
CRATE = ROOT / "nix/rust-shell-probe"
CASES = ("route-timeout", "configure-resize", "buffer-release", "touch-cancel")


def cargo_test(name):
    subprocess.run(["cargo", "test", "--locked", name], cwd=CRATE, check=True,
                   stdout=subprocess.DEVNULL)


def route_timeout():
    subprocess.run(["cargo", "build", "--locked", "--quiet"], cwd=CRATE, check=True)
    binary = CRATE / "target/debug/k230-shell-rust-probe"
    with tempfile.TemporaryDirectory() as directory:
        runtime = Path(directory)
        os.chmod(runtime, 0o700)
        path = runtime / "k230-shell-rust-probe.sock"
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(path))
        server.listen(1)
        env = os.environ | {"XDG_RUNTIME_DIR": str(runtime)}
        start = time.monotonic()
        result = subprocess.run([binary, "--surface", "drawer"], env=env,
                                capture_output=True, timeout=2)
        elapsed = time.monotonic() - start
        assert result.returncode != 0 and 0.35 <= elapsed < 0.9, (result, elapsed)
        invalid = subprocess.run([binary, "--surface", "browser"], env=env,
                                 capture_output=True, timeout=2)
        assert invalid.returncode != 0
        server.close()
        path.unlink()
        split = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        split.bind(str(path))
        split.listen(1)

        def reply_in_parts():
            with split.accept()[0] as peer:
                assert peer.recv(24) == b"shade\n"
                peer.sendall(b"O")
                time.sleep(0.03)
                peer.sendall(b"K\n")

        worker = threading.Thread(target=reply_in_parts)
        worker.start()
        accepted = subprocess.run([binary, "--surface", "shade"], env=env,
                                  capture_output=True, timeout=2)
        worker.join(timeout=2)
        assert accepted.returncode == 0, accepted.stderr.decode()
        split.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", choices=CASES)
    cases = parser.parse_args().case or CASES
    for case in cases:
        if case == "route-timeout":
            route_timeout()
        elif case == "configure-resize":
            cargo_test("configure_size_is_bounded")
        elif case == "buffer-release":
            cargo_test("buffer_release_gate")
        elif case == "touch-cancel":
            cargo_test("touch_cancel_does_not_turn_into_tap")
        print(f"PASS {case}")


if __name__ == "__main__":
    main()
