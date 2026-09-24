#!/usr/bin/env python3
"""Private, root-owned Wi-Fi Settings broker. Never log requests or command output.

The shell is an unprivileged client. SSIDs and passphrases enter only through the
private Unix socket; fixed process arguments contain neither. The real radio
backend is kept separate from the protocol so host tests need no radio or root.
"""
import argparse
import hashlib
import grp
import json
import os
from pathlib import Path
import pwd
import re
import select
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time

MAX_REQUEST = 4096
MAX_RESPONSE = 16384
MAX_NETWORKS = 48
MAX_SAVED = 8
MAX_SCAN_BYTES = 256 * 1024
SOCKET_TIMEOUT = 3
CONNECT_TIMEOUT = 22


class WifiError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def ssid_value(value):
    if not isinstance(value, str) or not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise WifiError("invalid-network")
    if len(value.encode("utf-8")) > 32:
        raise WifiError("invalid-network")
    return value


def password_value(value):
    if not isinstance(value, str) or not 8 <= len(value) <= 63 or not value.isascii():
        raise WifiError("invalid-password")
    if any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise WifiError("invalid-password")
    return value


def config_for(ssid, security, password=None, control="/run/k230-wifi/wpa_supplicant"):
    ssid = ssid_value(ssid)
    if security not in ("open", "wpa2-psk"):
        raise WifiError("unsupported-security")
    if security == "open":
        if password not in (None, ""):
            raise WifiError("invalid-password")
        key = "key_mgmt=NONE"
    else:
        password = password_value(password)
        key = "psk=" + hashlib.pbkdf2_hmac("sha1", password.encode("ascii"), ssid.encode("utf-8"), 4096, 32).hex()
    return (f"ctrl_interface=DIR={control} GROUP=root\n"
            "update_config=0\nnetwork={\n"
            f"    ssid={ssid.encode('utf-8').hex()}\n"
            f"    {key}\n"
            "}\n").encode("ascii")


def block_identity(block):
    try:
        raw = re.search(rb"(?m)^\s*ssid=([0-9a-fA-F]{2,64})\s*$", block)
        quoted = re.search(rb'(?m)^\s*ssid="((?:[^"\\]|\\["\\])+)"\s*$', block)
        if raw:
            ssid = bytes.fromhex(raw.group(1).decode("ascii")).decode("utf-8")
        elif quoted:
            ssid = quoted.group(1).replace(b'\\"', b'"').replace(b'\\\\', b'\\').decode("utf-8")
        else:
            return None
        ssid_value(ssid)
        if re.search(rb"(?m)^\s*key_mgmt=NONE\s*$", block):
            security = "open"
        elif re.search(rb"(?m)^\s*psk=", block):
            security = "wpa2-psk"
        else:
            security = "unsupported"
        return {"ssid": ssid, "security": security}
    except (UnicodeError, ValueError, WifiError):
        return None


def parse_saved(data):
    """Preserve bounded root-owned stanzas byte-for-byte; fail closed on unknown global data."""
    if data is None:
        return []
    if len(data) > 8192:
        raise WifiError("unsupported-saved-config")
    allowed = (b"ctrl_interface=DIR=/run/k230-wifi/wpa_supplicant GROUP=root",
               b"update_config=0")
    blocks = []
    current = None
    for line in data.splitlines(keepends=True):
        stripped = line.strip()
        if current is None:
            if stripped == b"network={":
                current = [line]
            elif not stripped or stripped.startswith(b"#") or stripped in allowed:
                continue
            else:
                raise WifiError("unsupported-saved-config")
        else:
            if stripped == b"network={":
                raise WifiError("unsupported-saved-config")
            current.append(line)
            if stripped == b"}":
                raw = b"".join(current)
                identity = block_identity(raw)
                if identity is None:
                    raise WifiError("unsupported-saved-config")
                blocks.append((identity, raw))
                if len(blocks) > MAX_SAVED:
                    raise WifiError("saved-limit")
                current = None
    if current is not None:
        raise WifiError("unsupported-saved-config")
    names = [identity["ssid"] for identity, _ in blocks]
    if len(names) != len(set(names)):
        raise WifiError("unsupported-saved-config")
    return blocks


def merge_saved(previous, ssid, security, password):
    existing = [(identity, raw) for identity, raw in parse_saved(previous)
                if identity["ssid"] != ssid]
    if len(existing) >= MAX_SAVED:
        raise WifiError("saved-limit")
    selected = config_for(ssid, security, password).split(b"network={", 1)[1]
    blocks = [raw if raw.endswith(b"\n") else raw + b"\n" for _, raw in existing]
    blocks.append(b"network={" + selected)
    return (b"ctrl_interface=DIR=/run/k230-wifi/wpa_supplicant GROUP=root\n"
            b"update_config=0\n" + b"".join(blocks))


def parse_scan(output):
    """Accept visible UTF-8 open/RSN-PSK BSSs; never emit BSSID or raw scan lines."""
    if len(output) > MAX_SCAN_BYTES:
        raise WifiError("scan-too-large")
    rows = {}
    item = None
    def finish(entry):
        if not entry or not entry["ssid"]:
            return
        try:
            ssid = ssid_value(entry["ssid"])
        except WifiError:
            return
        if entry["privacy"] and entry["rsn_psk"]:
            security = "wpa2-psk"
        elif entry["privacy"]:
            security = "unsupported"
        else:
            security = "open"
        old = rows.get(ssid)
        if old is None or old["security"] == "unsupported":
            rows[ssid] = {"ssid": ssid, "security": security}
    for raw in output.decode("utf-8", "replace").splitlines():
        line = raw.lstrip()
        if line.startswith("BSS "):
            finish(item)
            item = {"ssid": "", "privacy": False, "rsn_psk": False, "rsn": False}
        elif item is not None:
            if line.startswith("SSID: "):
                item["ssid"] = line[6:]
            elif line.startswith("capability:") and "Privacy" in line:
                item["privacy"] = True
            elif line.startswith("RSN:"):
                item["rsn"] = True
            elif item["rsn"] and line.lstrip("* ").startswith("Authentication suites:") and "PSK" in line:
                item["rsn_psk"] = True
    finish(item)
    return sorted(rows.values(), key=lambda row: row["ssid"].casefold())[:MAX_NETWORKS]


def parse_link(output):
    if len(output) > 8192:
        raise WifiError("link-too-large")
    text = output.decode("utf-8", "replace")
    if "Not connected." in text:
        return None
    match = re.search(r"(?m)^\s*SSID: (.+)$", text)
    if not match:
        return None
    try:
        return ssid_value(match.group(1))
    except WifiError:
        return None


def candidate_completed(output, ssid):
    if len(output) > 8192:
        return False
    fields = dict(line.split("=", 1) for line in output.decode("utf-8", "replace").splitlines()
                  if "=" in line)
    return fields.get("wpa_state") == "COMPLETED" and fields.get("ssid") == ssid


class Radio:
    def __init__(self, credential=Path("/var/lib/k230/wifi/wpa_supplicant.conf"),
                 runtime=Path("/run/k230-wifi-settings"),
                 iw="iw", supplicant="wpa_supplicant", wpa_cli="wpa_cli", systemctl="systemctl",
                 owner_uid=0):
        self.credential = Path(credential)
        self.runtime = Path(runtime)
        self.iw = iw
        self.supplicant = supplicant
        self.wpa_cli = wpa_cli
        self.systemctl = systemctl
        self.owner_uid = owner_uid

    def previous_config(self):
        try:
            info = self.credential.lstat()
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(info.st_mode) or info.st_uid != self.owner_uid or info.st_mode & 0o177 or info.st_size > 8192:
            raise WifiError("unsafe-credential")
        fd = os.open(self.credential, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            data = os.read(fd, 8193)
            if len(data) > 8192:
                raise WifiError("unsafe-credential")
            return data
        finally:
            os.close(fd)

    def fixed(self, argv, timeout=5):
        process = None
        try:
            process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL)
            result = bytearray()
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise WifiError("radio-timeout")
                ready, _, _ = select.select([process.stdout], [], [], remaining)
                if not ready:
                    raise WifiError("radio-timeout")
                chunk = os.read(process.stdout.fileno(), min(8192, MAX_SCAN_BYTES + 1 - len(result)))
                if not chunk:
                    break
                result.extend(chunk)
                if len(result) > MAX_SCAN_BYTES:
                    raise WifiError("response-too-large")
            if process.wait(timeout=max(0.01, deadline - time.monotonic())):
                raise WifiError("radio-unavailable")
            return bytes(result)
        except (OSError, subprocess.TimeoutExpired):
            raise WifiError("radio-unavailable") from None
        finally:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=2)
                process.stdout.close()

    def arm_restore(self):
        script = Path(__file__).resolve(strict=True)
        self.fixed(["systemd-run", "--unit=k230-wifi-settings-restore",
                    "--on-active=35s", "--collect", sys.executable, str(script), "--restore"])

    def cancel_restore(self):
        self.fixed([self.systemctl, "stop", "k230-wifi-settings-restore.timer"])

    def saved(self):
        return [identity for identity, _ in parse_saved(self.previous_config())]

    def scan(self):
        return parse_scan(self.fixed([self.iw, "dev", "wlan0", "scan"], timeout=12))

    def status(self):
        try:
            current = parse_link(self.fixed([self.iw, "dev", "wlan0", "link"]))
            error = None
        except WifiError as exc:
            current, error = None, exc.code
        try:
            saved = self.saved()
        except (WifiError, OSError):
            saved = []
            error = "unsupported-saved-config"
        return {"current": current, "saved": saved, "error": error}

    def connect(self, ssid, security, password, cancelled=lambda: False):
        self.runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.runtime.stat().st_uid != self.owner_uid or self.runtime.stat().st_mode & 0o077:
            raise WifiError("unsafe-runtime")
        fd, name = tempfile.mkstemp(prefix="candidate-", dir=self.runtime)
        path = Path(name)
        process = None
        stopped = False
        accepted = False
        persisted = False
        watchdog = False
        previous = None
        try:
            previous = self.previous_config()
            candidate = config_for(ssid, security, password, str(self.runtime / "control"))
            merged = merge_saved(previous, ssid, security, password)
            if cancelled():
                raise WifiError("cancelled")
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(candidate)
                stream.flush()
                os.fsync(stream.fileno())
            # A separate systemd timer restores the old service if this broker
            # crashes or stalls after stopping it. The candidate remains in
            # this broker service cgroup, which the restore helper stops first.
            self.arm_restore()
            watchdog = True
            # The persistent service and candidate must never own wlan0 together.
            self.fixed([self.systemctl, "stop", "k230-wifi.service"])
            stopped = True
            control = self.runtime / "control"
            control.mkdir(mode=0o700, exist_ok=True)
            (self.runtime / "client").mkdir(mode=0o700, exist_ok=True)
            process = subprocess.Popen([self.supplicant, "-q", "-i", "wlan0", "-c", str(path)],
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
            deadline = time.monotonic() + CONNECT_TIMEOUT
            while time.monotonic() < deadline:
                if cancelled():
                    raise WifiError("cancelled")
                if process.poll() is not None:
                    raise WifiError("authentication-failed")
                try:
                    status = self.fixed([self.wpa_cli, "-s", str(self.runtime / "client"),
                                         "-p", str(control), "-i", "wlan0", "status"], timeout=2)
                except WifiError:
                    status = b""
                if candidate_completed(status, ssid):
                    accepted = True
                    break
                time.sleep(0.5)
            if not accepted:
                raise WifiError("connection-timeout")
            if cancelled():
                raise WifiError("cancelled")
            persisted = True  # _persist can fail after atomic replacement.
            try:
                self._persist(merged)
            except (OSError, WifiError):
                if previous is None:
                    self.credential.unlink(missing_ok=True)
                else:
                    self._persist(previous)
                persisted = False
                raise WifiError("save-failed") from None
            return {"result": "saved", "ssid": ssid}
        finally:
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            path.unlink(missing_ok=True)
            if stopped:
                try:
                    self.fixed([self.systemctl, "start", "k230-wifi.service"])
                except WifiError:
                    if persisted:
                        if previous is None:
                            self.credential.unlink(missing_ok=True)
                        else:
                            self._persist(previous)
                        persisted = False
                    # Retain the independent timer to retry restoration.
                    raise WifiError("service-restart-failed") from None
            if watchdog:
                self.cancel_restore()

    def _persist(self, data):
        directory = self.credential.parent
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != self.owner_uid or info.st_mode & 0o077:
            raise WifiError("unsafe-credential")
        fd, name = tempfile.mkstemp(prefix=".wifi-", dir=directory)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.credential)
            dfd = os.open(directory, os.O_DIRECTORY | os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        finally:
            Path(name).unlink(missing_ok=True)

    def forget(self, ssid):
        ssid_value(ssid)
        previous = self.previous_config()
        blocks = parse_saved(previous)
        if not any(identity["ssid"] == ssid for identity, _ in blocks):
            raise WifiError("not-saved")
        remaining = [raw if raw.endswith(b"\n") else raw + b"\n" for identity, raw in blocks
                     if identity["ssid"] != ssid]
        new_data = (b"ctrl_interface=DIR=/run/k230-wifi/wpa_supplicant GROUP=root\n"
                    b"update_config=0\n" + b"".join(remaining))
        self.arm_restore()
        safe_to_cancel = False
        try:
            self.fixed([self.systemctl, "stop", "k230-wifi.service"])
            try:
                if remaining:
                    self._persist(new_data)
                else:
                    self.credential.unlink()
                self.fixed([self.systemctl, "start", "k230-wifi.service"])
                safe_to_cancel = True
            except (OSError, WifiError):
                self._persist(previous)
                self.fixed([self.systemctl, "start", "k230-wifi.service"])
                safe_to_cancel = True
                raise WifiError("forget-failed") from None
        finally:
            if safe_to_cancel:
                self.cancel_restore()
        return {"result": "forgotten"}


class Broker:
    def __init__(self, radio, allowed_uid):
        self.radio = radio
        self.allowed_uid = allowed_uid
        self.busy = False
        self.last_scan = 0.0

    def handle(self, uid, data, cancelled=lambda: False):
        if uid != self.allowed_uid:
            return {"schema": 1, "state": "failed", "error": "denied"}
        try:
            if len(data) > MAX_REQUEST:
                raise WifiError("request-too-large")
            request = json.loads(data)
            if not isinstance(request, dict) or request.get("schema") != 1:
                raise WifiError("invalid-request")
            op = request.get("op")
            if op == "status":
                result = self.radio.status()
            elif op == "scan":
                now = time.monotonic()
                if now - self.last_scan < 3:
                    raise WifiError("scan-too-soon")
                self.last_scan = now
                result = {"networks": self.radio.scan(), **self.radio.status()}
            elif op == "connect":
                result = self.radio.connect(request.get("ssid"), request.get("security"),
                                            request.get("password"), cancelled)
            elif op == "forget":
                result = self.radio.forget(request.get("ssid"))
            else:
                raise WifiError("unknown-operation")
            return {"schema": 1, "state": "ok", **result}
        except (WifiError, ValueError, TypeError, UnicodeError, OSError, subprocess.TimeoutExpired) as exc:
            code = exc.code if isinstance(exc, WifiError) else (
                "service-unavailable" if isinstance(exc, (OSError, subprocess.TimeoutExpired)) else "invalid-request")
            return {"schema": 1, "state": "failed", "error": code}


def peer_closed(conn):
    """An idle connected peer is not cancellation, even on timeout-mode sockets."""
    try:
        readable, _, _ = select.select([conn], [], [], 0)
        if not readable:
            return False
        return not conn.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT)
    except BlockingIOError:
        return False
    except OSError:
        return True


def serve(path, allowed_uid, allowed_gid, radio):
    path = Path(path)
    parent = path.parent
    info = parent.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
            or info.st_gid != allowed_gid or info.st_mode & 0o007):
        raise PermissionError("unsafe broker directory")
    if path.exists() or path.is_symlink():
        raise FileExistsError("broker socket already exists")
    broker = Broker(radio, allowed_uid)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(path))
        os.chown(path, 0, allowed_gid)
        os.chmod(path, 0o660)
        listener.listen(4)
        while True:
            conn, _ = listener.accept()
            with conn:
                conn.settimeout(SOCKET_TIMEOUT)
                peer = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
                uid = struct.unpack("3i", peer)[1]
                try:
                    if uid != allowed_uid:
                        conn.sendall(b'{"schema":1,"state":"failed","error":"denied"}\n')
                        continue
                    payload = bytearray()
                    deadline = time.monotonic() + SOCKET_TIMEOUT
                    while b"\n" not in payload and len(payload) <= MAX_REQUEST:
                        if time.monotonic() >= deadline:
                            raise TimeoutError()
                        conn.settimeout(max(0.01, deadline - time.monotonic()))
                        chunk = conn.recv(min(1024, MAX_REQUEST + 1 - len(payload)))
                        if not chunk:
                            break
                        payload.extend(chunk)
                    if b"\n" in payload:
                        end = payload.index(b"\n")
                        if end + 1 != len(payload):
                            conn.sendall(b'{"schema":1,"state":"failed","error":"invalid-request"}\n')
                            continue
                        payload = payload[:end]
                    answer = broker.handle(uid, payload, lambda: peer_closed(conn))
                    encoded = json.dumps(answer, separators=(",", ":")).encode("utf-8")
                    if len(encoded) > MAX_RESPONSE:
                        encoded = b'{"schema":1,"state":"failed","error":"response-too-large"}'
                    conn.sendall(encoded + b"\n")
                except (OSError, TimeoutError):
                    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--socket", default="/run/k230-wifi-settings/broker.sock")
    parser.add_argument("--shell-user", default="shell")
    parser.add_argument("--shell-group", default="shell")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit("broker needs root")
    if args.restore:
        # Invoked only by the separately scheduled root timer. No request
        # data or credential ever enters these arguments.
        def restore_step(operation, service):
            return subprocess.run(["systemctl", operation, service],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, timeout=5, check=False).returncode == 0
        if not restore_step("stop", "k230-wifi-settings.service"):
            raise SystemExit("could not stop candidate owner")
        restore_step("start", "k230-wifi.service")
        restore_step("start", "k230-wifi-settings.service")
        return
    shell_uid = pwd.getpwnam(args.shell_user).pw_uid
    shell_gid = grp.getgrnam(args.shell_group).gr_gid
    if shell_uid <= 0 or shell_gid <= 0:
        raise SystemExit("broker needs root and a nonroot shell UID")
    serve(args.socket, shell_uid, shell_gid,
          Radio(runtime=Path(args.socket).parent / "private"))


if __name__ == "__main__":
    main()
