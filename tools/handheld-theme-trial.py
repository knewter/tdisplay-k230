#!/usr/bin/env python3
"""Reserved-board theme trial. Public output is fixed; raw captures stay private.

Run as the shell user inside its active Wayland session. The operator owns the
board reservation and keeps the private runtime directory off the evidence
export. This script never switches system generations or sends remote traffic.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import tempfile
import time

from theme_preferences import _publish as publish_preferences, _read as read_preferences
from theme_transaction import (
    TransactionError, _pointer, _public_links, _swap_pointer,
    activate_generation, exchange,
)

STORE = re.compile(r"/nix/store/[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._?=-]+(?:/[A-Za-z0-9+._/-]+)?\Z")
IDENTITY = re.compile(r"[a-f0-9]{24}\Z")
REVISION = re.compile(r"[a-f0-9]{40}\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
LABEL = re.compile(r"[a-z0-9][a-z0-9._-]{0,79}\Z")
MAX_JSON = 1024 * 1024


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def store_path(value: str) -> Path:
    if not isinstance(value, str) or not STORE.fullmatch(value) or ".." in Path(value).parts:
        raise ValueError("manifest needs an explicit Nix store path")
    return Path(value)


def candidate(path: Path) -> dict:
    if path.stat().st_size > 16 * 1024:
        raise ValueError("candidate manifest exceeds bound")
    raw = json.loads(path.read_text())
    required = {"schema", "source_revision", "system", "theme_command", "capture_command",
                "default_generation", "state_root", "rust_socket", "deck_socket",
                "workload", "themes"}
    if not isinstance(raw, dict) or set(raw) != required or raw["schema"] != 1:
        raise ValueError("invalid candidate manifest fields")
    if not REVISION.fullmatch(raw["source_revision"]):
        raise ValueError("invalid source revision")
    for key in ("system", "theme_command", "capture_command", "default_generation"):
        store_path(raw[key])
    if not IDENTITY.fullmatch(Path(raw["default_generation"]).name):
        raise ValueError("invalid default generation")
    for key in ("state_root", "rust_socket", "deck_socket"):
        value = raw[key]
        if not isinstance(value, str) or not Path(value).is_absolute() or ".." in Path(value).parts:
            raise ValueError(f"invalid {key}")
    workload = raw["workload"]
    if (not isinstance(workload, dict) or set(workload) != {"id", "sha256", "artifact"}
            or not LABEL.fullmatch(workload["id"]) or not SHA256.fullmatch(workload["sha256"])):
        raise ValueError("invalid shared workload identity")
    if not isinstance(workload["artifact"], str) or not Path(workload["artifact"]).is_absolute():
        raise ValueError("workload artifact must be absolute")
    themes = raw["themes"]
    if not isinstance(themes, dict) or not {"dark", "light"}.issubset(themes) or set(themes) - {"dark", "light", "community"}:
        raise ValueError("candidate needs dark and light roles")
    for role, name in themes.items():
        if not isinstance(name, str) or not LABEL.fullmatch(name):
            raise ValueError(f"invalid {role} theme name")
    return raw


def fixed_json(data: bytes) -> dict:
    if len(data) > MAX_JSON:
        raise RuntimeError("theme response exceeds bound")
    value = json.loads(data)
    if not isinstance(value, dict) or value.get("schema") != 1:
        raise RuntimeError("theme response schema mismatch")
    return value


def command(arguments: list[str]) -> dict:
    result = subprocess.run(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=30, check=False)
    if result.returncode:
        # Never emit stderr: it may contain private clone paths.
        raise RuntimeError("theme command failed")
    return fixed_json(result.stdout)


def save_private(path: Path, value: dict) -> None:
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def app_pointer(state_root: Path) -> Path | None:
    link = state_root / "app-appearance/active"
    if not link.is_symlink():
        if link.exists():
            raise TransactionError("incompatible app appearance pointer")
        return None
    target = link.resolve(strict=True)
    allowed = (state_root / "app-appearance/generations").resolve(strict=True)
    if target.parent != allowed or not target.is_dir():
        raise TransactionError("app appearance pointer escapes private generations")
    return target


def restore_app_pointer(state_root: Path, previous: str | None) -> None:
    link = state_root / "app-appearance/active"
    target = Path(previous) if previous is not None else None
    if target is not None:
        allowed = (state_root / "app-appearance/generations").resolve(strict=True)
        if target.resolve(strict=True).parent != allowed:
            raise TransactionError("saved app appearance escaped private generations")
        link.parent.mkdir(mode=0o700, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".restore-", dir=link.parent) as temporary:
            replacement = Path(temporary) / "active"
            replacement.symlink_to(target)
            os.replace(replacement, link)
    elif link.is_symlink():
        link.unlink()
    elif link.exists():
        raise TransactionError("incompatible app appearance pointer")


def write_public(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".new")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def restore_default(state_root: Path, missing_links: list[str], endpoints: tuple[Path, Path],
                    transport=exchange) -> None:
    """Return from a trial activation to no pointer and both pinned defaults."""
    descriptor = os.open(state_root / ".activation.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        deadline = time.monotonic() + 2.0
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as error:
                if time.monotonic() >= deadline:
                    raise TransactionError("default restoration lock timed out") from error
                time.sleep(0.01)
        current = _pointer(state_root)
        try:
            for endpoint in endpoints:
                transport(endpoint, "rollback", None)
            _swap_pointer(state_root, None)
            for name in missing_links:
                link = state_root / name
                if link.is_symlink() and os.readlink(link) == "active/" + name:
                    link.unlink()
        except Exception as error:
            failed = False
            for endpoint in endpoints:
                try:
                    transport(endpoint, "rollback", current)
                except Exception:
                    failed = True
            if current is not None:
                _swap_pointer(state_root, current)
            raise TransactionError("default restoration failed" + ("; scene uncertain" if failed else "")) from error
    finally:
        os.close(descriptor)


def restore(snapshot: dict, *, state_root: Path, default_generation: Path,
            endpoints: tuple[Path, Path], transport=exchange,
            app_sync=None) -> None:
    previous = Path(snapshot["previous"]) if snapshot["previous"] is not None else None
    if previous is None:
        restore_default(state_root, snapshot["missing_links"], endpoints, transport)
    else:
        options = {"state_root": state_root, "endpoint": endpoints[0],
                   "endpoints": endpoints, "transport": transport}
        if app_sync is not None:
            options["app_sync"] = app_sync
        activate_generation(previous, **options)
    contents = (base64.b64decode(snapshot["preferences"], validate=True)
                if snapshot["preferences"] is not None else None)
    # Preferences are private. The board operator reserves theme activation
    # during this trial; publish is atomic and restores exact prior bytes.
    publish_preferences(state_root, contents)
    restore_app_pointer(state_root, snapshot["app_appearance"])
    for name in snapshot["missing_links"]:
        link = state_root / name
        if link.is_symlink() and os.readlink(link) == "active/" + name:
            link.unlink()
    if _pointer(state_root) != previous:
        raise TransactionError("restored pointer differs from baseline")
    if app_pointer(state_root) != (Path(snapshot["app_appearance"]) if snapshot["app_appearance"] else None):
        raise TransactionError("restored app appearance differs from baseline")
    if previous is None and not default_generation.is_dir():
        raise TransactionError("pinned default disappeared")


class Trial:
    def __init__(self, manifest: dict, *, call=command, capture=None,
                 transport=exchange, app_sync=None):
        self.m = manifest
        self.call = call
        self.capture = capture or self.capture_native
        self.transport = transport
        self.app_sync = app_sync

    def capture_native(self, role: str, raw: Path) -> dict:
        image = raw / (role + ".png")
        # Shell ACK precedes the managed Foot follower's one-second poll.
        # Allow that asynchronous consumer to paint before a static capture;
        # this delay is not a presentation-latency measurement or acceptance.
        time.sleep(1.25)
        result = subprocess.run([self.m["capture_command"], "-t", "png", str(image)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=15, check=False)
        if result.returncode or not image.is_file() or image.stat().st_size > 16 * 1024 * 1024:
            raise RuntimeError("native capture failed")
        image.chmod(0o600)
        return {"kind": "native-unreviewed", "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                "bytes": image.stat().st_size}

    def theme(self, action: str, *args: str) -> dict:
        # Pin the state root and both ACK endpoints to the same candidate used
        # for restoration, independently of HOME or wrapper defaults.
        return self.call([self.m["theme_command"], "--state-root", self.m["state_root"],
                          "--rust-socket", self.m["rust_socket"],
                          "--deck-socket", self.m["deck_socket"],
                          action, *args, "--json"])

    def run(self, output: Path, raw: Path) -> dict:
        workload = self.m["workload"]
        artifact = Path(workload["artifact"])
        metadata = artifact.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 64 * 1024:
            raise RuntimeError("unsafe workload artifact")
        if hashlib.sha256(artifact.read_bytes()).hexdigest() != workload["sha256"]:
            raise RuntimeError("workload artifact changed")
        public_workload = {"id": workload["id"], "sha256": workload["sha256"]}
        state = Path(self.m["state_root"])
        endpoints = (Path(self.m["rust_socket"]), Path(self.m["deck_socket"]))
        default = Path(self.m["default_generation"])
        if not state.is_dir() or not default.is_dir():
            raise RuntimeError("state root or default generation unavailable")
        previous = _pointer(state)
        preferences, _ = read_preferences(state)
        missing = [path.name for path in _public_links(state)]
        previous_app = app_pointer(state)
        snapshot = {"previous": str(previous) if previous else None,
                    "preferences": base64.b64encode(preferences).decode() if preferences else None,
                    "missing_links": missing,
                    "app_appearance": str(previous_app) if previous_app else None}
        save_private(raw / "recovery.json", snapshot)
        public = {"schema": 1, "source_revision": self.m["source_revision"],
                  "system": self.m["system"], "workload": public_workload,
                  "started_utc": utc(), "arms": [], "restoration": "pending",
                  "physical_observation": "UNVERIFIED"}
        write_public(output / "result.json", public)
        error = None
        stage = "list"
        try:
            listing = self.theme("list")
            entries = listing.get("themes")
            if not isinstance(entries, list) or len(entries) > 512:
                raise RuntimeError("invalid theme list")
            stage = "baseline-capture"
            public["baseline"] = {"generation": previous.name if previous else default.name,
                                  "capture": self.capture("baseline", raw),
                                  "workload": public_workload}
            write_public(output / "result.json", public)
            for role, name in self.m["themes"].items():
                stage = "select-" + role
                matches = [item for item in entries if isinstance(item, dict)
                           and item.get("name") == name and
                           item.get("origin") == ("user" if role == "community" else "builtin")]
                if len(matches) != 1 or not IDENTITY.fullmatch(str(matches[0].get("id", ""))):
                    raise RuntimeError("requested theme is absent or ambiguous")
                theme_id = matches[0]["id"]
                stage = "preview-" + role
                preview = self.theme("preview", theme_id)
                generation = preview.get("generation")
                if not isinstance(generation, str) or not IDENTITY.fullmatch(generation):
                    raise RuntimeError("invalid preview generation")
                backgrounds = preview.get("backgrounds")
                if not isinstance(backgrounds, list) or len(backgrounds) > 512:
                    raise RuntimeError("invalid preview backgrounds")
                selected = [row for row in backgrounds if isinstance(row, dict) and row.get("selected") is True]
                if len(selected) != 1 or not IDENTITY.fullmatch(str(selected[0].get("id", ""))):
                    raise RuntimeError("preview lacks one selected background")
                stage = "activate-" + role
                activated = self.theme("activate", theme_id, "--expected-generation", generation)
                if activated.get("activated") is not True or activated.get("generation") != generation:
                    raise RuntimeError("activation did not acknowledge preview generation")
                active = self.theme("list").get("active")
                if not isinstance(active, dict) or active.get("generation") != generation:
                    raise RuntimeError("active generation differs from activation")
                stage = "capture-" + role
                app_status = activated.get("app_appearance")
                app_state = app_status.get("state") if isinstance(app_status, dict) else None
                if app_state not in ("applied", "failed", "superseded"):
                    app_state = "unknown"
                arm = {"role": role, "theme_id": theme_id, "generation": generation,
                       "selected_background_id": selected[0]["id"],
                       "background_count": len(backgrounds), "workload": public_workload,
                       "capture": self.capture(role, raw),
                       "app_appearance_state": app_state}
                public["arms"].append(arm)
                write_public(output / "result.json", public)
        except Exception as caught:
            error = caught
            public["trial"] = "failed"
            public["failure_stage"] = stage
        finally:
            try:
                restore(snapshot, state_root=state, default_generation=default,
                        endpoints=endpoints, transport=self.transport, app_sync=self.app_sync)
                public["restoration"] = "passed"
                public["restored_generation"] = previous.name if previous else default.name
            except Exception:
                public["restoration"] = "FAILED"
                error = RuntimeError("theme restoration failed; use private recovery.json")
            else:
                try:
                    public["restored_capture"] = self.capture("restored", raw)
                except Exception:
                    public["restored_capture"] = "failed"
                    error = RuntimeError("restored capture failed")
            public["finished_utc"] = utc()
            write_public(output / "result.json", public)
        if error:
            raise RuntimeError("trial failed; inspect fixed result and private recovery") from error
        public["trial"] = "completed-needs-operator-review"
        write_public(output / "result.json", public)
        return public


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--raw-private-dir", type=Path)
    parser.add_argument("--restore-private-dir", type=Path,
                        help="manually restore from an interrupted trial's private recovery.json")
    args = parser.parse_args()
    try:
        manifest = candidate(args.candidate_manifest)
        if platform.machine() != "riscv64":
            raise RuntimeError("execution requires the reserved RISC-V board session")
        if Path("/run/current-system").resolve(strict=True) != Path(manifest["system"]):
            raise RuntimeError("installed system differs from candidate manifest")
        if args.restore_private_dir is not None:
            recovery = args.restore_private_dir / "recovery.json"
            if recovery.is_symlink() or not recovery.is_file() or recovery.stat().st_mode & 0o077 or recovery.stat().st_size > 16 * 1024:
                raise RuntimeError("unsafe private recovery record")
            snapshot = json.loads(recovery.read_text())
            restore(snapshot, state_root=Path(manifest["state_root"]),
                    default_generation=Path(manifest["default_generation"]),
                    endpoints=(Path(manifest["rust_socket"]), Path(manifest["deck_socket"])))
            print("previous theme, wallpaper preferences and app appearance restored")
            return 0
        if args.output is None:
            raise RuntimeError("--output is required for a trial")
        if args.output.exists():
            raise RuntimeError("output directory already exists")
        runtime = Path(os.environ["XDG_RUNTIME_DIR"]).resolve(strict=True)
        if runtime.stat().st_uid != os.geteuid() or runtime.stat().st_mode & 0o077:
            raise RuntimeError("runtime directory is not private and owned")
        args.output.mkdir(mode=0o700, parents=True)
        raw = args.raw_private_dir or Path(tempfile.mkdtemp(prefix="k230-theme-trial-", dir=runtime))
        if args.raw_private_dir is not None:
            raw.mkdir(mode=0o700)
        resolved_raw = raw.resolve(strict=True)
        if (not resolved_raw.is_relative_to(runtime) or resolved_raw.is_relative_to(args.output.resolve())
                or raw.stat().st_uid != os.geteuid() or raw.stat().st_mode & 0o077):
            raise RuntimeError("raw directory must be owned and private under XDG_RUNTIME_DIR")
        Trial(manifest).run(args.output, raw)
        print(f"fixed public result: {args.output / 'result.json'}")
        print(f"private raw captures and recovery: {raw}")
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, TransactionError, subprocess.TimeoutExpired) as error:
        print(f"theme trial failed: {type(error).__name__}; inspect private recovery and fixed result", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
