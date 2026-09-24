"""Check the installed launcher route request without a compositor or board."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def build_client(temp):
    layer = ROOT / "tests/fixtures/wayland/wlr-layer-shell-unstable-v1.xml"
    xdg = Path("/usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml")
    if not xdg.is_file():
        matches = list(Path("/nix/store").glob("*-wayland-protocols-*/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml"))
        if not matches:
            raise RuntimeError("wayland-protocols xdg-shell.xml is unavailable")
        xdg = matches[0]
    generated = []
    for name, xml in (("wlr-layer-shell-unstable-v1", layer), ("xdg-shell", xdg)):
        header = temp / f"{name}-client-protocol.h"
        code = temp / f"{name}-protocol.c"
        subprocess.run(["wayland-scanner", "client-header", str(xml), str(header)], check=True)
        subprocess.run(["wayland-scanner", "private-code", str(xml), str(code)], check=True)
        generated.append(code)
    flags = subprocess.check_output(["pkg-config", "--cflags", "--libs", "wayland-client",
                                     "gio-unix-2.0", "json-glib-1.0", "pangocairo", "librsvg-2.0"], text=True).split()
    executable = temp / "k230-touch-launcher"
    subprocess.run(["cc", "-std=c11", "-O1", "-Wall",
                    "-DK230_CATALOG_LIBRARY", "-I", str(temp), "-I", str(ROOT / "nix/touch-launcher"),
                    *(str(ROOT / "nix/touch-launcher" / name) for name in
                      ("touch-launcher.c", "appearance.c", "catalog.c", "icon.c")),
                    *(str(code) for code in generated), "-o", str(executable), *flags, "-lm", "-lrt"], check=True)
    return executable


def test_route_socket(executable, runtime):
    path = runtime / "k230-shell-route.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    server.listen(1)
    requests = []

    def reply():
        conn, _ = server.accept()
        with conn:
            requests.append(conn.recv(24))
            conn.sendall(b"OK\n")

    thread = threading.Thread(target=reply, daemon=True)
    thread.start()
    env = {**os.environ, "XDG_RUNTIME_DIR": str(runtime)}
    completed = subprocess.run([str(executable), "--surface", "drawer"], env=env,
                               timeout=2, capture_output=True)
    thread.join(timeout=2)
    assert completed.returncode == 0, completed.stderr.decode()
    assert requests == [b"drawer\n"]
    assert subprocess.run([str(executable), "--surface", "browser"], env=env,
                          timeout=2, capture_output=True).returncode == 2
    server.close()
    path.unlink()
    assert subprocess.run([str(executable), "--surface", "drawer"], env=env,
                          timeout=2, capture_output=True).returncode == 1
    silent = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    silent.bind(str(path))
    silent.listen(1)
    before = time.monotonic()
    result = subprocess.run([str(executable), "--surface", "drawer"], env=env,
                            timeout=2, capture_output=True)
    elapsed = time.monotonic() - before
    assert result.returncode == 1 and elapsed < 0.9, (result.returncode, elapsed)
    silent.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", choices=["route-socket"])
    parser.parse_args()
    with tempfile.TemporaryDirectory() as name:
        temp = Path(name)
        executable = build_client(temp)
        test_route_socket(executable, temp)
    print("PASS route-socket")


if __name__ == "__main__":
    main()
