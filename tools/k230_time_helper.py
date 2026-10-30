#!/usr/bin/env python3
"""Apply the time zone or network time for Settings, and nothing else.

systemd starts one instance per connection on /run/k230-time.sock
(`Accept=yes`, owner root, group shell, mode 0660), with the connection as
stdin and stdout. The instance reads one request line, answers one line and
exits, so nothing stays resident between requests.

Requests (one line, at most 128 bytes):

    zone <name>          a zone listed in zone1970.tab, or UTC
    network-time on|off

Answers: `ok`, or `error <reason>`. Only the configured user (the shell) is
answered; any other peer gets `error peer`. The zone is applied through
`timedatectl set-timezone`, so timedated still writes /etc/localtime. Network
time is a flag file that systemd-timesyncd's unit is conditioned on, plus a
start or stop, so the choice survives a reboot without enabling or disabling
unit files (NixOS keeps those read-only).
"""
import argparse
import os
import pwd
import re
import socket
import struct
import subprocess
import sys
from pathlib import Path

MAX_REQUEST = 128
ZONE_SHAPE = re.compile(r"^[A-Za-z][A-Za-z0-9_+-]*(/[A-Za-z0-9][A-Za-z0-9_+-]*){0,2}$")
TIMESYNCD = "systemd-timesyncd.service"


def allowed_zones(zoneinfo):
    """Canonical zone names from tzdata's zone1970.tab, plus UTC."""
    zones = {"UTC"}
    try:
        text = (Path(zoneinfo) / "zone1970.tab").read_text()
    except OSError:
        return zones
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) >= 3:
            zones.add(fields[2].strip())
    return zones


def parse(line):
    """`("zone", name)` or `("network-time", on)`, else None."""
    words = line.split()
    if len(words) != 2:
        return None
    verb, arg = words
    if verb == "zone" and ZONE_SHAPE.match(arg) and ".." not in arg:
        return ("zone", arg)
    if verb == "network-time" and arg in ("on", "off"):
        return ("network-time", arg == "on")
    return None


def handle(line, zoneinfo, flag, run):
    """The answer for one request; `run` executes an argv as root."""
    request = parse(line)
    if request is None:
        return "error request"
    kind, value = request
    if kind == "zone":
        if value not in allowed_zones(zoneinfo) or not (Path(zoneinfo) / value).is_file():
            return "error zone"
        return "ok" if run(["timedatectl", "set-timezone", value]) else "error apply"
    flag = Path(flag)
    try:
        if value:
            flag.unlink(missing_ok=True)
        else:
            flag.parent.mkdir(parents=True, exist_ok=True)
            flag.write_text("off\n")
    except OSError:
        return "error state"
    return "ok" if run(["systemctl", "start" if value else "stop", TIMESYNCD]) else "error apply"


def peer_uid(sock):
    creds = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    return struct.unpack("3i", creds)[1]


def read_line(sock):
    data = b""
    while b"\n" not in data and len(data) <= MAX_REQUEST:
        chunk = sock.recv(MAX_REQUEST + 1 - len(data))
        if not chunk:
            break
        data += chunk
    if len(data) > MAX_REQUEST:
        return None
    try:
        return data.split(b"\n", 1)[0].decode("ascii")
    except UnicodeDecodeError:
        return None


def run_command(argv):
    return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=20).returncode == 0


def serve(sock, user_uid, zoneinfo, flag, run=run_command):
    if peer_uid(sock) != user_uid:
        answer = "error peer"
    else:
        line = read_line(sock)
        answer = "error request" if line is None else handle(line, zoneinfo, flag, run)
    sock.sendall(answer.encode() + b"\n")
    return answer


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--user", required=True, help="the only peer answered")
    parser.add_argument("--zoneinfo", default="/etc/zoneinfo")
    parser.add_argument("--flag", default="/var/lib/k230-time/network-time-off")
    args = parser.parse_args(argv)
    sock = socket.socket(fileno=os.dup(0))
    answer = serve(sock, pwd.getpwnam(args.user).pw_uid, args.zoneinfo, args.flag)
    print(f"k230-time: {answer}", file=sys.stderr)
    return 0 if answer == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
