"""Host-side transaction transport for a future shell appearance receiver.

The receiver is not installed yet. This module never treats socket existence as
proof of a live shell: every phase needs an explicit matching acknowledgement.
"""

import fcntl
import json
import os
from pathlib import Path
import socket
import tempfile
import time


class TransactionError(Exception):
    pass


MAX_REPLY = 4096


def exchange(endpoint: Path, phase: str, generation: Path | None, *, timeout: float = 2.0) -> None:
    identity = generation.name if generation is not None else None
    message = {"protocol": 1, "phase": phase, "generation": identity,
               "path": str(generation) if generation is not None else None}
    if phase == "prepare" and generation is not None:
        pointer = generation.parent.parent / "active"
        previous = pointer.resolve(strict=True) if pointer.is_symlink() else None
        message["previous_generation"] = previous.name if previous is not None else None
        message["previous_path"] = str(previous) if previous is not None else None
    deadline = time.monotonic() + timeout
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(max(0.001, deadline - time.monotonic()))
        connection.connect(str(endpoint))
        connection.settimeout(max(0.001, deadline - time.monotonic()))
        connection.sendall(json.dumps(message, sort_keys=True).encode() + b"\n")
        data = bytearray()
        while not data.endswith(b"\n"):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransactionError(f"{phase} acknowledgement timed out")
            connection.settimeout(remaining)
            chunk = connection.recv(1)
            if not chunk or len(data) >= MAX_REPLY:
                raise TransactionError(f"invalid {phase} acknowledgement")
            data.extend(chunk)
    try:
        reply = json.loads(data)
    except (ValueError, UnicodeDecodeError) as error:
        raise TransactionError(f"invalid {phase} acknowledgement") from error
    if (not isinstance(reply, dict) or reply.get("protocol") != 1
            or reply.get("phase") != phase or reply.get("generation") != identity
            or reply.get("status") != "ok"):
        raise TransactionError(f"shell rejected {phase}")


def _pointer(root: Path) -> Path | None:
    pointer = root / "active"
    if not pointer.is_symlink():
        if pointer.exists():
            raise TransactionError("active generation is not a symlink")
        return None
    target = pointer.resolve(strict=True)
    if not target.is_relative_to(root / "generations") or not target.is_dir():
        raise TransactionError("active generation escapes cache")
    return target


def _swap_pointer(root: Path, generation: Path | None) -> None:
    pointer = root / "active"
    if generation is None:
        pointer.unlink(missing_ok=True)
    else:
        with tempfile.TemporaryDirectory(prefix=".link-", dir=root) as temporary:
            candidate = Path(temporary) / "active"
            candidate.symlink_to(generation)
            os.replace(candidate, pointer)
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def activate_generation(generation: Path, *, state_root: Path, endpoint: Path,
                        transport=exchange, lock_timeout: float = 2.0) -> None:
    """Publish one prepared generation only after phase-checked shell acks.

    The lock covers the whole transaction, including failure recovery. The
    future shell receiver must implement prepare/commit/rollback as one scene
    generation protocol; these host fakes do not prove that it does so.
    """
    state_root = state_root.resolve(strict=True)
    generations = state_root / "generations"
    generation = generation.resolve(strict=True)
    if (not generation.is_relative_to(generations.resolve(strict=True))
            or not (generation / "report.json").is_file()):
        raise TransactionError("generation is outside the prepared cache")
    descriptor = os.open(state_root / ".activation.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        deadline = time.monotonic() + lock_timeout
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as error:
                if time.monotonic() >= deadline:
                    raise TransactionError("activation lock timed out") from error
                time.sleep(min(0.01, max(0, deadline - time.monotonic())))
        previous = _pointer(state_root)
        transport(endpoint, "prepare", generation)
        try:
            _swap_pointer(state_root, generation)
            transport(endpoint, "commit", generation)
        except Exception as error:
            try:
                _swap_pointer(state_root, previous)
            except Exception as pointer_error:
                raise TransactionError("commit failed and pointer restoration failed") from pointer_error
            try:
                transport(endpoint, "rollback", previous)
            except Exception as rollback_error:
                raise TransactionError("commit failed and shell rollback was not acknowledged") from rollback_error
            raise TransactionError("commit failed; previous generation restored") from error
    finally:
        os.close(descriptor)
