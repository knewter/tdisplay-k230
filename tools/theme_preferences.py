"""Bounded per-source wallpaper memory for acknowledged theme activations.

The caller invokes an intent under theme_transaction's existing activation
lock. Preparing or previewing only reads this state; no clone is modified.
"""

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile


MAX_BYTES = 65536
MAX_CHOICES = 256
FILENAME = "background-selections.json"


class PreferenceError(ValueError):
    pass


def _key(source: Path) -> str:
    return hashlib.sha256(os.fsencode(source.resolve(strict=False))).hexdigest()


def _path(state_root: Path) -> Path:
    return state_root / FILENAME


def _read(state_root: Path) -> tuple[bytes | None, dict]:
    path = _path(state_root)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None, {}
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_BYTES:
        raise PreferenceError("wallpaper preferences are unsafe or oversized")
    original = path.read_bytes()
    if len(original) > MAX_BYTES:
        raise PreferenceError("wallpaper preferences changed while reading")
    try:
        data = json.loads(original)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PreferenceError("invalid wallpaper preferences") from error
    if (not isinstance(data, dict) or data.get("version") != 1
            or not isinstance(data.get("choices"), dict)
            or len(data["choices"]) > MAX_CHOICES):
        raise PreferenceError("invalid wallpaper preferences")
    for key, value in data["choices"].items():
        if (not isinstance(key, str) or len(key) != 64
                or any(char not in "0123456789abcdef" for char in key)
                or not isinstance(value, str) or len(value) > 256
                or not value.startswith("backgrounds/") or not value[12:]
                or "/" in value[12:]
                or value in ("backgrounds/.", "backgrounds/..")):
            raise PreferenceError("invalid wallpaper preference entry")
    return original, data["choices"]


def choice(state_root: Path, source: Path) -> str | None:
    return _read(state_root)[1].get(_key(source))


def _publish(state_root: Path, contents: bytes | None) -> None:
    path = _path(state_root)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise PreferenceError("incompatible wallpaper preference path")
    if contents is None:
        path.unlink(missing_ok=True)
    else:
        descriptor, temporary = tempfile.mkstemp(prefix=".wallpaper-", dir=state_root)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    directory = os.open(state_root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


class SelectionIntent:
    def __init__(self, state_root: Path, source: Path, selected: str | None,
                 available: list[str], explicit: bool):
        self.state_root = state_root
        self.key = _key(source)
        self.selected = selected
        self.available = frozenset(available)
        self.explicit = explicit
        self.original = None
        self.before = None
        self.attempted = False
        if selected is not None and selected not in self.available:
            raise PreferenceError("selected wallpaper is not in prepared theme")

    def guard(self) -> None:
        self.original, self.before = _read(self.state_root)
        current = self.before.get(self.key)
        if not self.explicit and current in self.available and current != self.selected:
            raise PreferenceError("wallpaper selection changed; preview again")

    def commit(self) -> None:
        if self.before is None:
            raise PreferenceError("wallpaper preference was not guarded")
        updated = dict(self.before)
        if self.selected is None:
            updated.pop(self.key, None)
        else:
            updated[self.key] = self.selected
        if len(updated) > MAX_CHOICES:
            raise PreferenceError("too many remembered wallpapers")
        contents = (json.dumps({"version": 1, "choices": updated},
                               sort_keys=True, separators=(",", ":")) + "\n").encode()
        if len(contents) > MAX_BYTES:
            raise PreferenceError("wallpaper preferences exceed bound")
        self.attempted = True
        _publish(self.state_root, contents)

    def rollback(self) -> None:
        if self.attempted:
            _publish(self.state_root, self.original)
