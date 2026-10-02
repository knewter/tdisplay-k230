#!/usr/bin/env python3
"""Reserved-board theme trial. Public output is fixed; raw captures stay private.

Run as the shell user inside its active Wayland session. The operator owns the
board reservation and keeps private captures/recovery off the evidence export.
Reboot checkpoints use persistent private storage and require operator reboots.
This script never switches system generations or sends remote traffic.
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
from theme_background_metrics import measure as measure_background_resources
from theme_background_status import expected_fingerprint, progress as video_progress, read_status

STORE = re.compile(r"/nix/store/[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._?=-]+(?:/[A-Za-z0-9+._/-]+)?\Z")
IDENTITY = re.compile(r"[a-f0-9]{24}\Z")
REVISION = re.compile(r"[a-f0-9]{40}\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
BOOT_ID = re.compile(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}\Z")
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
    if not isinstance(raw, dict) or not required.issubset(raw) or set(raw) - required - {"background_trial", "reboot_trial"} or raw["schema"] != 1:
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
    if "background_trial" in raw:
        trial = raw["background_trial"]
        if not isinstance(trial, dict) or set(trial) != {"duration_seconds", "interval_seconds", "choices"}:
            raise ValueError("invalid background trial fields")
        duration, interval = trial["duration_seconds"], trial["interval_seconds"]
        if (isinstance(duration, bool) or not isinstance(duration, (int, float))
                or isinstance(interval, bool) or not isinstance(interval, (int, float))
                or not 2 <= duration <= 60 or not .1 <= interval <= 1):
            raise ValueError("background trial sampling exceeds bound")
        choices = trial["choices"]
        if not isinstance(choices, dict) or set(choices) != {"static", "video"}:
            raise ValueError("background trial needs static and video choices")
        for choice in choices.values():
            if (not isinstance(choice, dict)
                    or set(choice) != {"theme_name", "origin", "background_id"}
                    or not isinstance(choice["theme_name"], str)
                    or not LABEL.fullmatch(choice["theme_name"])
                    or choice["origin"] not in ("builtin", "user")
                    or not isinstance(choice["background_id"], str)
                    or not IDENTITY.fullmatch(choice["background_id"])):
                raise ValueError("invalid background trial choice")
    if "reboot_trial" in raw:
        choice = raw["reboot_trial"]
        if (not isinstance(choice, dict) or set(choice) != {"theme_name", "background_id"}
                or not isinstance(choice["theme_name"], str)
                or not LABEL.fullmatch(choice["theme_name"])
                or not isinstance(choice["background_id"], str)
                or not IDENTITY.fullmatch(choice["background_id"])):
            raise ValueError("invalid reboot trial choice")
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
                 transport=exchange, app_sync=None,
                 resource_sample=measure_background_resources,
                 status_reader=read_status, status_path: Path | None = None,
                 status_wait_s: float = 3.0):
        self.m = manifest
        self.call = call
        self.capture = capture or self.capture_native
        self.transport = transport
        self.app_sync = app_sync
        self.resource_sample = resource_sample
        self.status_reader = status_reader
        self.status_path = status_path
        self.status_wait_s = status_wait_s

    def video_status(self, generation: str, fingerprint: str) -> dict:
        path = self.status_path
        if path is None:
            runtime = os.environ.get("XDG_RUNTIME_DIR")
            if not runtime or not Path(runtime).is_absolute():
                raise RuntimeError("wallpaper status runtime is unavailable")
            path = Path(runtime) / "k230-wallpaper-status.json"
        deadline = time.monotonic() + self.status_wait_s
        while True:
            try:
                return self.status_reader(path, generation, fingerprint)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                if time.monotonic() >= deadline:
                    raise RuntimeError("matching private wallpaper playback status unavailable") from error
                time.sleep(0.1)

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

    def run(self, output: Path, raw: Path, workload_mode: str = "themes") -> dict:
        if workload_mode not in ("themes", "backgrounds"):
            raise ValueError("unknown theme workload mode")
        background_trial = self.m.get("background_trial") if workload_mode == "backgrounds" else None
        if workload_mode == "backgrounds" and background_trial is None:
            raise ValueError("background workload needs pinned trial choices")
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
                  "workload_mode": workload_mode,
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
            if background_trial is not None:
                public["baseline"]["resources"] = self.resource_sample(
                    background_trial["duration_seconds"], background_trial["interval_seconds"])
            write_public(output / "result.json", public)
            arms = ([(role, name, None, None) for role, name in self.m["themes"].items()]
                    if background_trial is None else
                    [(role, choice["theme_name"], choice["background_id"], choice["origin"])
                     for role, choice in background_trial["choices"].items()])
            for role, name, background_id, origin in arms:
                stage = "select-" + role
                matches = [item for item in entries if isinstance(item, dict)
                           and item.get("name") == name and
                           item.get("origin") == (origin or ("user" if role == "community" else "builtin"))]
                if len(matches) != 1 or not IDENTITY.fullmatch(str(matches[0].get("id", ""))):
                    raise RuntimeError("requested theme is absent or ambiguous")
                theme_id = matches[0]["id"]
                stage = "preview-" + role
                background_arg = ("--background", background_id) if background_id else ()
                preview = self.theme("preview", theme_id, *background_arg)
                generation = preview.get("generation")
                if not isinstance(generation, str) or not IDENTITY.fullmatch(generation):
                    raise RuntimeError("invalid preview generation")
                backgrounds = preview.get("backgrounds")
                if not isinstance(backgrounds, list) or len(backgrounds) > 512:
                    raise RuntimeError("invalid preview backgrounds")
                selected = [row for row in backgrounds if isinstance(row, dict) and row.get("selected") is True]
                if len(selected) != 1 or not IDENTITY.fullmatch(str(selected[0].get("id", ""))):
                    raise RuntimeError("preview lacks one selected background")
                if background_id and selected[0]["id"] != background_id:
                    raise RuntimeError("preview selected a different background")
                if background_trial is not None and selected[0].get("kind") != ("image" if role == "static" else "video"):
                    raise RuntimeError("background trial choice has wrong media kind")
                stage = "activate-" + role
                activated = self.theme("activate", theme_id, *background_arg,
                                       "--expected-generation", generation)
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
                if background_trial is not None:
                    stage = "measure-" + role
                    if role == "video":
                        active_generation = _pointer(state)
                        if active_generation is None or active_generation.name != generation:
                            raise RuntimeError("video generation pointer differs from activation")
                        fingerprint = expected_fingerprint(
                            generation, active_generation / "report.json")
                        before_video = self.video_status(generation, fingerprint)
                    arm["resources"] = self.resource_sample(
                        background_trial["duration_seconds"], background_trial["interval_seconds"])
                    if role == "video":
                        after_video = self.video_status(generation, fingerprint)
                        counts = video_progress(before_video, after_video)
                        second = self.capture("video-second", raw)
                        if second["sha256"] == arm["capture"]["sha256"]:
                            raise RuntimeError("two native wallpaper captures are identical")
                        arm["playback"] = {"source": "private-wallpaper-status-v1",
                                           "frame_deltas": counts,
                                           "native_captures_distinct": True,
                                           "second_capture": second,
                                           "limits": "Wayland callbacks and changing native captures do not prove panel presentation."}
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



def boot_identity() -> str:
    value = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    if not BOOT_ID.fullmatch(value):
        raise RuntimeError("invalid boot identity")
    return value


def manifest_identity(manifest: dict) -> str:
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()


def private_record(path: Path) -> dict:
    metadata = path.lstat()
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid()
            or metadata.st_mode & 0o077 or metadata.st_size > 128 * 1024):
        raise RuntimeError("unsafe private reboot record")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError("invalid private reboot record")
    return value


def durable_move(source: Path, destination: Path) -> None:
    # Renames retain the complete original directory, including consumers'
    # private state. No copied approximation of production state is restored.
    if destination.exists() or destination.is_symlink():
        raise RuntimeError("reboot backup destination already exists")
    source.rename(destination)
    for parent in {source.parent, destination.parent}:
        descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


class RebootTrial(Trial):
    """One bounded step per invocation; the reserved operator performs reboots.

    The fresh-state arm empties the entire theme state subtree, not the user's
    entire home. Its result must be supplemented by a true fresh-home trial.
    """
    def __init__(self, manifest: dict, *, boot_reader=boot_identity, **kwargs):
        super().__init__(manifest, **kwargs)
        self.boot_reader = boot_reader

    def theme(self, action: str, *args: str) -> dict:
        return self.call([self.m["theme_command"], "--state-root", self.m["state_root"],
                          "--rust-socket", self.m["rust_socket"],
                          "--deck-socket", self.m["deck_socket"],
                          # The installed helper pins its own catalog and
                          # ignores per-call roots. Force the real CLI parser
                          # so this dedicated fixture cannot hit that daemon.
                          "--helper-socket", str(self.private / "disabled-helper.sock"),
                          "--user-themes", str(self.private / "sources"),
                          action, *args, "--json"])

    def checkpoint(self, record: dict) -> None:
        write_public(self.private / "reboot.json", record)
        descriptor = os.open(self.private / "reboot.json", os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        descriptor = os.open(self.private, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def bind(self, private: Path) -> None:
        if "reboot_trial" not in self.m:
            raise ValueError("reboot workload needs pinned trial choice")
        metadata = private.lstat()
        if (not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.geteuid()
                or metadata.st_mode & 0o077 or private.resolve() != private):
            raise RuntimeError("reboot directory must be owned, private and canonical")
        self.private = private
        self.state = Path(self.m["state_root"])
        if (self.state.is_symlink() or self.state.resolve() != self.state
                or private.is_relative_to(self.state) or self.state.is_relative_to(private)
                or self.state.parent.stat().st_dev != metadata.st_dev):
            raise RuntimeError("state and private backups need separate paths on one filesystem")
        self.source = private / "sources" / self.m["reboot_trial"]["theme_name"]
        if (private / "disabled-helper.sock").exists():
            raise RuntimeError("trial helper socket must be absent")

    def load(self) -> dict:
        record = private_record(self.private / "reboot.json")
        if (record.get("protocol") != "reboot-v1"
                or record.get("manifest_sha256") != manifest_identity(self.m)):
            raise RuntimeError("reboot candidate identity mismatch")
        return record

    def recover(self, private: Path) -> None:
        self.bind(private)
        record = self.load()
        if record.get("restoration") == "passed":
            return
        if (private / "held-source").exists():
            durable_move(private / "held-source", self.source)
        if (private / "normal-state").exists():
            if self.state.exists():
                durable_move(self.state, private / "displaced-state")
            durable_move(private / "normal-state", self.state)
        snapshot = private_record(private / "recovery.json")
        restore(snapshot, state_root=self.state,
                default_generation=Path(self.m["default_generation"]),
                endpoints=(Path(self.m["rust_socket"]), Path(self.m["deck_socket"])),
                transport=self.transport, app_sync=self.app_sync)
        record["restoration"] = "passed"
        self.checkpoint(record)

    def empty_state(self) -> None:
        self.state.mkdir(mode=0o700)
        (self.state / "generations").mkdir(mode=0o700)

    def observed(self) -> dict:
        pointer = _pointer(self.state)
        preferences, _ = read_preferences(self.state)
        if pointer is None:
            return {"generation": None,
                    "preferences_sha256": hashlib.sha256(preferences or b"").hexdigest()}
        report = pointer / "report.json"
        if report.stat().st_size > MAX_JSON:
            raise RuntimeError("active report exceeds bound")
        data = json.loads(report.read_text())
        if data.get("generation") != pointer.name or not IDENTITY.fullmatch(pointer.name):
            raise RuntimeError("active report generation mismatch")
        return {"generation": pointer.name,
                "background_fingerprint": expected_fingerprint(pointer.name, report),
                "preferences_sha256": hashlib.sha256(preferences or b"").hexdigest()}

    def listing(self) -> dict:
        value = self.theme("list")
        active = value.get("active")
        if (not isinstance(value.get("themes"), list) or len(value["themes"]) > 512
                or not isinstance(active, dict) or not {"id", "generation"}.issubset(active)
                or any(active[key] is not None and (not isinstance(active[key], str)
                       or not IDENTITY.fullmatch(active[key])) for key in ("id", "generation"))):
            raise RuntimeError("invalid reboot catalog response")
        return value

    def run_step(self, output: Path, private: Path, phase: str) -> dict:
        self.bind(private)
        if (output.resolve() != output or output.is_relative_to(private)
                or private.is_relative_to(output) or output.is_relative_to(self.state)
                or self.state.is_relative_to(output)):
            raise RuntimeError("reboot output must be separate from state and private backups")
        boot = self.boot_reader()
        if not isinstance(boot, str) or not BOOT_ID.fullmatch(boot):
            raise RuntimeError("invalid boot identity")
        workload = self.m["workload"]
        artifact = Path(workload["artifact"])
        metadata = artifact.lstat()
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 64 * 1024
                or hashlib.sha256(artifact.read_bytes()).hexdigest() != workload["sha256"]):
            raise RuntimeError("workload artifact changed")
        if phase == "begin":
            if (private / "reboot.json").exists() or (output / "result.json").exists():
                raise RuntimeError("reboot trial already exists")
            if (not self.source.is_dir() or self.source.is_symlink()
                    or self.source.resolve() != self.source):
                raise RuntimeError("trial-owned source fixture unavailable")
            if not self.state.is_dir() or not Path(self.m["default_generation"]).is_dir():
                raise RuntimeError("state root or pinned default unavailable")
            previous = _pointer(self.state)
            preferences, _ = read_preferences(self.state)
            previous_app = app_pointer(self.state)
            snapshot = {"previous": str(previous) if previous else None,
                        "preferences": base64.b64encode(preferences).decode() if preferences is not None else None,
                        "missing_links": [p.name for p in _public_links(self.state)],
                        "app_appearance": str(previous_app) if previous_app else None}
            save_private(private / "recovery.json", snapshot)
            record = {"protocol": "reboot-v1", "manifest_sha256": manifest_identity(self.m),
                      "boot_id": boot, "pending": "preparation", "restoration": "pending"}
            self.checkpoint(record)
            public = {"schema": 1, "source_revision": self.m["source_revision"],
                      "system": self.m["system"], "workload_mode": "reboot",
                      "workload": {"id": workload["id"], "sha256": workload["sha256"]},
                      "started_utc": utc(), "boots": [], "arms": [], "restoration": "pending",
                      "physical_observation": "UNVERIFIED", "fresh_home": "UNVERIFIED",
                      "evidence_class": "filesystem-and-cli-state-only",
                      "limits": "Theme-state reset is not a full fresh home; native captures need panel and console review."}
        elif phase == "resume":
            record = self.load()
            if record["restoration"] != "pending" or record["pending"] not in (
                    "remembered", "fresh-theme-state", "unavailable-source"):
                raise RuntimeError("reboot trial is not awaiting a boot")
            if boot == record["boot_id"]:
                raise RuntimeError("resume requires a different boot identity")
            public = private_record(output / "result.json")
            if (public.get("system") != self.m["system"]
                    or public.get("source_revision") != self.m["source_revision"]):
                raise RuntimeError("public reboot identity mismatch")
            if boot in {row.get("boot_id") for row in public.get("boots", [])}:
                raise RuntimeError("resume boot identity was already recorded")
        else:
            raise ValueError("invalid reboot phase")
        stage = record["pending"]
        public["boots"].append({"phase": "baseline" if phase == "begin" else stage,
                                "boot_id": boot, "system": self.m["system"], "observed_utc": utc()})
        try:
            if phase == "begin":
                public["baseline_capture"] = self.capture("baseline", private)
                durable_move(self.state, private / "normal-state")
                self.empty_state()
                listing = self.listing()
                entries = listing.get("themes", [])
                matches = [item for item in entries if item.get("name") == self.m["reboot_trial"]["theme_name"]
                           and item.get("origin") == "user"]
                if len(matches) != 1 or not IDENTITY.fullmatch(str(matches[0].get("id", ""))):
                    raise RuntimeError("trial source missing or ambiguous")
                theme_id = matches[0]["id"]
                background = self.m["reboot_trial"]["background_id"]
                preview = self.theme("preview", theme_id, "--background", background)
                generation = preview.get("generation")
                if not isinstance(generation, str) or not IDENTITY.fullmatch(generation):
                    raise RuntimeError("invalid reboot preview generation")
                selected = [row for row in preview.get("backgrounds", []) if row.get("selected") is True]
                if len(selected) != 1 or selected[0].get("id") != background:
                    raise RuntimeError("reboot preview background mismatch")
                activated = self.theme("activate", theme_id, "--background", background,
                                       "--expected-generation", generation)
                if activated.get("activated") is not True or activated.get("generation") != generation:
                    raise RuntimeError("reboot activation not acknowledged")
                expected = self.observed()
                if expected["generation"] != generation:
                    raise RuntimeError("reboot pointer differs from activation")
                record.update(expected=expected, theme_id=theme_id, background_id=background,
                              pending="remembered")
                public["prepared_capture"] = self.capture("prepared", private)
            else:
                observed = self.observed()
                listing = self.listing()
                if stage == "remembered":
                    if observed != record["expected"]:
                        raise RuntimeError("remembered theme or wallpaper changed across boot")
                    preview = self.theme("preview", record["theme_id"])
                    selected = [row for row in preview.get("backgrounds", []) if row.get("selected") is True]
                    if (preview.get("generation") != observed["generation"] or len(selected) != 1
                            or selected[0].get("id") != record["background_id"]):
                        raise RuntimeError("remembered wallpaper no longer selected by default")
                    public["arms"].append({"role": stage, "observed": observed,
                                           "capture": self.capture(stage, private), "gate": "state-check-passed"})
                    durable_move(self.state, private / "remembered-state")
                    self.empty_state()
                    record["pending"] = "fresh-theme-state"
                elif stage == "fresh-theme-state":
                    if (observed["generation"] is not None or read_preferences(self.state)[0] is not None
                            or app_pointer(self.state) is not None
                            or listing.get("active", {}).get("generation") is not None):
                        raise RuntimeError("fresh theme state did not use pinned default")
                    public["arms"].append({"role": stage, "expected_default_generation": Path(self.m["default_generation"]).name,
                                           "capture": self.capture(stage, private), "gate": "state-check-passed",
                                           "full_fresh_home": "UNVERIFIED"})
                    durable_move(self.state, private / "fresh-state")
                    durable_move(private / "remembered-state", self.state)
                    durable_move(self.source, private / "held-source")
                    record["pending"] = "unavailable-source"
                else:
                    public["arms"].append({"role": stage, "observed": observed,
                                           "capture": self.capture(stage, private), "gate": "pending"})
                    if (self.source.exists() or listing.get("active", {}).get("id") is not None
                            or observed["generation"] is not None):
                        public["arms"][-1]["gate"] = "failed-default-required"
                        raise RuntimeError("unavailable source did not recover to pinned default")
                    public["arms"][-1]["gate"] = "state-check-passed"
                    self.recover(private)
                    public["restoration"] = "passed"
                    public["restored_capture"] = self.capture("restored", private)
                    public["trial"] = "completed-needs-operator-review"
                    public["finished_utc"] = utc()
                    write_public(output / "result.json", public)
                    return public
            record["boot_id"] = boot
            self.checkpoint(record)
            public["trial"] = "awaiting-operator-reboot"
            public["next_phase"] = record["pending"]
            write_public(output / "result.json", public)
            return public
        except Exception as error:
            public.update(trial="failed", failure_stage=stage, finished_utc=utc())
            try:
                self.recover(private)
                public["restoration"] = "passed"
                public["restored_capture"] = self.capture("restored", private)
            except Exception:
                public["restoration"] = "FAILED"
            write_public(output / "result.json", public)
            raise RuntimeError("reboot trial failed; inspect fixed result and private recovery") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--raw-private-dir", type=Path)
    parser.add_argument("--workload", choices=("themes", "backgrounds", "reboot"), default="themes")
    parser.add_argument("--reboot-phase", choices=("begin", "resume"))
    parser.add_argument("--reboot-private-dir", type=Path,
                        help="existing persistent private directory with sources/NAME fixture")
    parser.add_argument("--restore-private-dir", type=Path,
                        help="manually restore from an interrupted trial's private recovery.json")
    args = parser.parse_args()
    try:
        manifest = candidate(args.candidate_manifest)
        if platform.machine() != "riscv64":
            raise RuntimeError("execution requires the reserved RISC-V board session")
        if Path("/run/current-system").resolve(strict=True) != Path(manifest["system"]):
            raise RuntimeError("installed system differs from candidate manifest")
        if args.workload == "reboot":
            private = args.restore_private_dir or args.reboot_private_dir
            if private is None or not private.is_absolute():
                raise RuntimeError("reboot needs an absolute persistent private directory")
            private = private.resolve(strict=True)
            if any(private.is_relative_to(Path(path)) for path in ("/run", "/tmp", "/var/tmp", "/nix", "/dev", "/proc", "/sys")):
                raise RuntimeError("reboot private directory must survive reboot outside transient paths")
            runner = RebootTrial(manifest)
            if args.restore_private_dir is not None:
                runner.recover(private)
                print("normal theme state restored; verify the normal panel/session")
                return 0
            if args.output is None or args.reboot_phase is None or args.raw_private_dir is not None:
                raise RuntimeError("reboot needs --output and --reboot-phase; captures use the persistent private directory")
            output = args.output.resolve()
            state = Path(manifest["state_root"]).resolve()
            if (output.is_relative_to(private) or private.is_relative_to(output)
                    or output.is_relative_to(state) or state.is_relative_to(output)
                    or any(output.is_relative_to(Path(path)) for path in ("/run", "/tmp", "/var/tmp"))):
                raise RuntimeError("reboot output needs a separate persistent path")
            if args.reboot_phase == "begin":
                if output.exists():
                    raise RuntimeError("output directory already exists")
                output.mkdir(mode=0o700, parents=True)
            elif not output.is_dir() or output.stat().st_uid != os.geteuid() or output.stat().st_mode & 0o077:
                raise RuntimeError("resume output must be owned and private")
            result = runner.run_step(output, private, args.reboot_phase)
            print("fixed public result written; " + result["trial"])
            return 0
        if args.reboot_phase is not None or args.reboot_private_dir is not None:
            raise RuntimeError("reboot options require --workload reboot")
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
        Trial(manifest).run(args.output, raw, workload_mode=args.workload)
        print(f"fixed public result: {args.output / 'result.json'}")
        print(f"private raw captures and recovery: {raw}")
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, TransactionError, subprocess.TimeoutExpired) as error:
        print(f"theme trial failed: {type(error).__name__}; inspect private recovery and fixed result", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
