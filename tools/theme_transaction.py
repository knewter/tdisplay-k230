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

import theme_timing


class TransactionError(Exception):
    pass


MAX_REPLY = 4096
# A receiver's own bounded work (decoding a full-size theme still, then waiting
# for a presentation slot) takes about 3 s on the K230's in-order core, so the
# former 2 s budget dropped legitimate acks mid-flight ("Broken pipe" in the
# Rust log). Keep this above the slowest receiver's internal bounds.
EXCHANGE_TIMEOUT_S = 8.0


#: Per-process, per-endpoint memory of the generation each receiver's own
#: `prepared` slot should currently hold, updated by every successful
#: exchange below -- the same transitions `appearance.rs`'s `respond()`
#: (and `nix/card-shell/appearance.c`'s `request()`) make to their own
#: `prepared`/`self.prepared` field: a successful "prepare" sets it, a
#: successful "commit" or "rollback" clears it (the receiver's own slot is
#: consumed the same way). `activate_generation()` reads this to skip a
#: "prepare" it already knows is redundant (board evidence: the Rust shell
#: re-received a "prepare" mid-Apply for a generation the chooser's own
#: prepare-ahead had already prepared moments earlier). Advisory only, like
#: everything else this comment's siblings describe as such: a stale entry
#: (some other process, such as the client's own subprocess fallback,
#: touched a receiver without this process knowing) only ever means
#: `activate_generation()` retries with a real prepare, per its own doc --
#: it can never cause a wrong commit, because the receiver's own protocol
#: check ("commit does not match prepared generation") still runs either
#: way and is what a retry there responds to.
_prepared_state: dict[Path, str] = {}


def _remember(endpoint: Path, phase: str, generation: Path | None) -> None:
    if phase == "prepare" and generation is not None:
        _prepared_state[endpoint] = generation.name
    elif phase in ("commit", "rollback"):
        _prepared_state.pop(endpoint, None)


def exchange(endpoint: Path, phase: str, generation: Path | None, *,
             timeout: float = EXCHANGE_TIMEOUT_S) -> None:
    identity = generation.name if generation is not None else None
    message = {"protocol": 1, "phase": phase, "generation": identity,
               "path": str(generation) if generation is not None else None}
    if phase == "prepare" and generation is not None:
        previous = _pointer(generation.parent.parent)
        message["previous_generation"] = previous.name if previous is not None else None
        message["previous_path"] = str(previous) if previous is not None else None
    deadline = time.monotonic() + timeout
    started = theme_timing.now_ms()
    try:
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
        _remember(endpoint, phase, generation)
    finally:
        # Named per-endpoint round-trip cost (coordinator's own question:
        # "how long does the Rust or deck ack take"). Logged unconditionally,
        # including on a timeout/rejection, since a slow *failing* exchange
        # is exactly as diagnostically interesting as a slow successful one.
        theme_timing.log("exchange", phase, endpoint=endpoint.name,
                         generation=identity or "-", ms=f"{theme_timing.now_ms() - started:.1f}")


def _pointer(root: Path) -> Path | None:
    pointer = root / "active"
    if not pointer.is_symlink():
        if pointer.exists():
            raise TransactionError("active generation is not a symlink")
        return None
    cache = (root / "generations").resolve(strict=True)
    raw = Path(os.readlink(pointer))
    normalized = (raw if raw.is_absolute() else pointer.parent / raw).resolve(strict=False)
    if not normalized.is_relative_to(cache):
        raise TransactionError("active generation escapes cache")
    try:
        target = pointer.resolve(strict=True)
    except FileNotFoundError:
        return None
    if not target.is_relative_to(cache) or not target.is_dir():
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


def _public_links(root: Path) -> list[Path]:
    missing = []
    for name in ("theme", "theme.name", "background"):
        path = root / name
        expected = "active/" + name
        if path.is_symlink():
            if os.readlink(path) != expected:
                raise TransactionError(f"incompatible public theme path: {name}")
        elif os.path.lexists(path):
            raise TransactionError(f"incompatible public theme path: {name}")
        else:
            missing.append(path)
    return missing


def prepare_only(generation: Path, *, state_root: Path, endpoint: Path,
                 transport=exchange, endpoints: tuple[Path, Path] | None = None) -> None:
    """Warm both appearance receivers' Prepare-phase state for `generation`
    without changing the active pointer and without a matching commit or
    rollback -- the clean hook a chooser UI calls as a person browses
    (e.g. once per newly-centred carousel candidate), so that a later
    `activate_generation()` for the *same* generation has its own internal
    Prepare arrive as a cache hit instead of a first decode.

    This is not a new mechanism: `activate_generation()` already sends this
    exact "prepare" message immediately before every commit
    (`nix/rust-shell-client/src/appearance.rs`'s Prepare handling already
    decodes/caches the wallpaper via `appearance_renderable()` at that
    point, before any commit). Calling it early, apart from a commit, only
    changes *when* that decode happens, matching `background.cache`'s own
    "advisory, never load-bearing for correctness" posture: `commit`'s own
    internal re-prepare (still sent by `activate_generation()` regardless
    of whether this ran first) is what the receiver actually validates
    against (`"commit does not match prepared generation"` in
    `appearance.rs`), so a stale, superseded, or never-issued warm-up can
    only cost time, never correctness.

    Each receiver keeps only its most recently prepared candidate (a
    single slot, matching `BackgroundCache`'s own single-slot design), so
    calling this again for a different generation while browsing simply
    replaces what was warmed -- there is no cache to explicitly evict and
    no lock to contend with an in-flight `activate_generation()` of a
    *different* generation (deliberately: a still-browsing person must
    never be blocked by, or block, someone else's unrelated commit).
    """
    state_root = state_root.resolve(strict=True)
    generations = state_root / "generations"
    generation = generation.resolve(strict=True)
    if (not generation.is_relative_to(generations.resolve(strict=True))
            or not (generation / "report.json").is_file()):
        raise TransactionError("generation is outside the prepared cache")
    if endpoints is None:
        targets = (endpoint,)
    else:
        if len(endpoints) != 2 or endpoints[0] == endpoints[1]:
            raise TransactionError("fanout requires two distinct appearance endpoints")
        targets = endpoints
    for target in targets:
        transport(target, "prepare", generation)


def activate_generation(generation: Path, *, state_root: Path, endpoint: Path,
                        transport=exchange, lock_timeout: float = 2.0,
                        preference=None, app_sync=None,
                        endpoints: tuple[Path, Path] | None = None) -> dict:
    """Publish one prepared generation only after phase-checked shell acks.

    The lock covers the whole transaction, including failure recovery. The
    future shell receiver must implement prepare/commit/rollback as one scene
    generation protocol; these host fakes do not prove that it does so.
    """
    stopwatch = theme_timing.Stopwatch()
    state_root = state_root.resolve(strict=True)
    generations = state_root / "generations"
    generation = generation.resolve(strict=True)
    if (not generation.is_relative_to(generations.resolve(strict=True))
            or not (generation / "report.json").is_file()):
        raise TransactionError("generation is outside the prepared cache")
    if endpoints is None:
        targets = (endpoint,)
    else:
        if len(endpoints) != 2 or endpoints[0] == endpoints[1]:
            raise TransactionError("fanout requires two distinct appearance endpoints")
        targets = endpoints
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
        stopwatch.lap("lock_wait")
        previous = _pointer(state_root)
        missing_links = _public_links(state_root)
        if preference is not None:
            preference.guard()
        stopwatch.lap("guard")
        # Skip a "prepare" this process already knows is redundant -- see
        # `_prepared_state`'s own doc. `warm` is exactly the targets this
        # optimism applies to; `commit` below retries those specifically
        # (and only those) with a real prepare if their commit turns out to
        # have been wrong to skip, so a stale assumption costs one extra
        # round trip, never a wrong or failed activation.
        warm = {target for target in targets if _prepared_state.get(target) == generation.name}
        to_prepare = [target for target in targets if target not in warm]
        if len(targets) == 2:
            def rollback_all():
                failures = []
                for target in targets:
                    try:
                        transport(target, "rollback", previous)
                    except Exception as error:
                        failures.append(error)
                return failures

            try:
                for target in to_prepare:
                    transport(target, "prepare", generation)
            except Exception as error:
                if rollback_all():
                    raise TransactionError("fanout prepare failed and rollback was not acknowledged") from error
                raise TransactionError("fanout prepare failed; both receivers restored") from error
        elif to_prepare:
            transport(endpoint, "prepare", generation)
        stopwatch.lap("prepare_phase")
        created_links = []
        try:
            _swap_pointer(state_root, generation)
            for path in missing_links:
                path.symlink_to("active/" + path.name)
                created_links.append(path)
            stopwatch.lap("swap_pointer")
            for target in targets:
                try:
                    transport(target, "commit", generation)
                except TransactionError:
                    if target not in warm:
                        raise
                    # This target's prepare was skipped as redundant, but
                    # its commit just disagreed (some other process,
                    # unknown to this one, touched this receiver since --
                    # see `_prepared_state`'s own doc). Retry once with a
                    # real prepare before treating this as a genuine commit
                    # failure; this is the only place a stale assumption
                    # here can cost anything, and it costs time, not
                    # correctness.
                    transport(target, "prepare", generation)
                    transport(target, "commit", generation)
            if preference is not None:
                preference.commit()
            stopwatch.lap("commit_phase")
            theme_timing.log("activate_generation", generation.name[:12], stopwatch,
                             warm=len(warm), targets=len(targets))
        except Exception as error:
            stopwatch.lap("commit_phase_failed")
            theme_timing.log("activate_generation", generation.name[:12], stopwatch,
                             warm=len(warm), targets=len(targets), outcome="rolling-back")
            preference_error = None
            pointer_error = None
            try:
                _swap_pointer(state_root, previous)
                for path in created_links:
                    if path.is_symlink() and os.readlink(path) == "active/" + path.name:
                        path.unlink()
            except Exception as restore_error:
                pointer_error = restore_error
            if preference is not None:
                try:
                    preference.rollback()
                except Exception as restore_error:
                    preference_error = restore_error
            if len(targets) == 2:
                rollback_errors = rollback_all()
                if rollback_errors:
                    raise TransactionError("commit failed and fanout rollback was not acknowledged") from rollback_errors[0]
            else:
                try:
                    transport(endpoint, "rollback", previous)
                except Exception as rollback_error:
                    raise TransactionError("commit failed and shell rollback was not acknowledged") from rollback_error
            if pointer_error is not None:
                raise TransactionError("commit failed and pointer restoration failed") from pointer_error
            if preference_error is not None:
                raise TransactionError("commit failed and wallpaper preference restoration failed") from preference_error
            raise TransactionError("commit failed; previous generation restored") from error
    finally:
        os.close(descriptor)
    # App refresh is a later phase. It must not convert an acknowledged shell
    # generation into a failed theme transaction or roll back the shell.
    # The adapter re-acquires this lock and refuses an outdated generation.
    from app_appearance import AppAppearanceSuperseded, sync as default_app_sync
    if app_sync is None:
        app_sync = default_app_sync
    try:
        app_sync(state_root, expected_generation=generation.name)
    except AppAppearanceSuperseded:
        return {"state": "superseded", "error": "newer-generation-active"}
    except Exception as error:
        return {"state": "failed", "error": "app-sync-failed",
                "kind": type(error).__name__}
    return {"state": "applied", "generation": generation.name}
