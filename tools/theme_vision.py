"""Vision-accessibility preference: a text-size step (100-200%) and a
high-contrast palette, applied to every theme generation.

The choice lives beside the theme state (`<state-root>/vision.json`) and is
baked into each prepared generation: the high-contrast palette replaces the
staged `colors.toml` before the templates run, and an `accessibility`
token section carries the text scale. The Rust shell and the card shell
both read that one generation, so they cannot disagree.
"""

import json
import os
from pathlib import Path
import stat
import tempfile


FILENAME = "vision.json"
MAX_BYTES = 4096
#: Text-size steps. 200% is WCAG 1.4.4's resize target; on this 331 ppi
#: panel the design body size (17-18 px) is about 8.5 sp, so 160% is roughly a
#: phone's default body text. "large" keeps its name and is now 130%.
TEXT_SCALES = {"default": 1.0, "large": 1.3, "larger": 1.6, "largest": 2.0}
CONTRASTS = ("standard", "high")
DEFAULT = {"text_scale": "default", "contrast": "standard"}

#: Replaces the theme's palette when contrast is "high": white text on
#: black, a yellow accent, and saturated status colours. Every key the
#: shell's templates read is present, so no theme colour leaks through.
HIGH_CONTRAST = {
    "background": "#000000", "foreground": "#ffffff", "accent": "#ffd700",
    "selection_background": "#ffd700", "selection_foreground": "#000000",
    "cursor": "#ffffff", "muted": "#e0e0e0",
    "color0": "#000000", "color1": "#ff5555", "color2": "#55ff55", "color3": "#ffff55",
    "color4": "#5599ff", "color5": "#ff55ff", "color6": "#55ffff", "color7": "#ffffff",
    "color8": "#c0c0c0", "color9": "#ff7777", "color10": "#77ff77", "color11": "#ffff77",
    "color12": "#77bbff", "color13": "#ff77ff", "color14": "#77ffff", "color15": "#ffffff",
}


class VisionError(ValueError):
    pass


def _path(state_root: Path) -> Path:
    return state_root / FILENAME


def validate(text_scale: object, contrast: object) -> dict:
    if text_scale not in TEXT_SCALES or contrast not in CONTRASTS:
        raise VisionError("invalid vision preference")
    return {"text_scale": text_scale, "contrast": contrast}


def load(state_root: Path) -> dict:
    """The saved choice, or the default when none was saved."""
    path = _path(state_root)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return dict(DEFAULT)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_BYTES:
        raise VisionError("vision preference is unsafe or oversized")
    try:
        data = json.loads(path.read_bytes()[:MAX_BYTES])
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VisionError("invalid vision preference") from error
    if not isinstance(data, dict) or data.get("version") != 1:
        raise VisionError("invalid vision preference")
    return validate(data.get("text_scale"), data.get("contrast"))


def save(state_root: Path, choice: dict) -> None:
    choice = validate(choice.get("text_scale"), choice.get("contrast"))
    state_root.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"version": 1, **choice}, sort_keys=True).encode() + b"\n"
    descriptor, temporary = tempfile.mkstemp(prefix=".vision-", dir=state_root)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, _path(state_root))
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def palette_text(original: str, choice: dict) -> str:
    """The staged `colors.toml` for `choice`: unchanged unless high contrast,
    which keeps the theme's other keys but overrides every listed colour."""
    if choice["contrast"] != "high":
        return original
    lines = [line for line in original.splitlines()
             if line.split("=", 1)[0].strip() not in HIGH_CONTRAST]
    lines += [f'{key} = "{value}"' for key, value in HIGH_CONTRAST.items()]
    return "\n".join(lines) + "\n"


def tokens(choice: dict) -> dict:
    """The `accessibility` section both renderers read."""
    return {"text-scale": {"kind": "number", "value": TEXT_SCALES[choice["text_scale"]]},
            "high-contrast": {"kind": "boolean", "value": choice["contrast"] == "high"}}
