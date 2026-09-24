"""Compile resolved Omarchy shell.toml data into bounded native token payloads.

Palette aliases and template precedence belong to the pinned upstream helpers.
This module only types their generated output for C/Cairo consumers.
"""

import math
import re


MAX_SECTIONS = 32
MAX_KEYS = 512
COLOR = re.compile(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?\Z")
RGBA = re.compile(r"rgba?\(\s*([0-9]+)\s*,\s*([0-9]+)\s*,\s*([0-9]+)(?:\s*,\s*([0-9]*\.?[0-9]+))?\s*\)\Z")
# Hyprland's own border/gradient syntax, distinct from the CSS decimal form
# above: a single compact hex run with no separating commas, alpha (if any)
# trailing the RGB bytes. Several built-in Omarchy themes (hackerman,
# last-horizon, solitude) set hyprland_active_border/hyprland_inactive_border
# this way, e.g. "rgba(26a269ee) rgba(2ec27eee) 45deg" or "rgb(1e1e1e)".
HEX_RGBA = re.compile(r"rgba\(\s*([0-9a-fA-F]{8})\s*\)\Z|rgb\(\s*([0-9a-fA-F]{6})\s*\)\Z")
PARTS = re.compile(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?|rgba?\([^)]*\)|[-+]?[0-9]*\.?[0-9]+deg")
REFERENCE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]*\.[a-zA-Z][a-zA-Z0-9_-]*\Z")
WIDTH_KEYS = re.compile(r"(?:^|-)border-width\Z")
SIDES = ("top", "right", "bottom", "left")


class TokenError(ValueError):
    pass


def _finite(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TokenError(f"{label} must be numeric")
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise TokenError(f"{label} out of range")
    return value


def _argb(value):
    if COLOR.fullmatch(value):
        digits = value[1:]
        return "#" + (digits[6:8] if len(digits) == 8 else "ff") + digits[:6].lower()
    hex_form = HEX_RGBA.fullmatch(value)
    if hex_form:
        digits = (hex_form.group(1) or hex_form.group(2)).lower()
        # Hyprland's rgba(RRGGBBAA) trails the alpha byte; rgb(RRGGBB) has none.
        return "#" + (digits[6:8] if len(digits) == 8 else "ff") + digits[:6]
    match = RGBA.fullmatch(value)
    if not match:
        raise TokenError(f"invalid color: {value[:40]}")
    rgb = [int(match.group(index)) for index in (1, 2, 3)]
    if any(channel > 255 for channel in rgb):
        raise TokenError("RGB channel out of range")
    alpha = _finite(float(match.group(4)) if match.group(4) is not None else 1.0,
                    0.0, 1.0, "RGBA alpha")
    return "#%02x%02x%02x%02x" % (round(alpha * 255), *rgb)


def _width(value, section, key):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        parts = [_finite(value, 0, 128, f"{section}.{key}")]
    elif isinstance(value, str):
        try:
            parts = [_finite(float(item), 0, 128, f"{section}.{key}") for item in value.split()]
        except ValueError as error:
            raise TokenError(f"invalid width: {section}.{key}") from error
    else:
        raise TokenError(f"invalid width: {section}.{key}")
    if len(parts) == 1:
        return [parts[0]] * 4
    if len(parts) == 2:
        return [parts[0], parts[1], parts[0], parts[1]]
    if len(parts) == 3:
        return [parts[0], parts[1], parts[2], parts[1]]
    if len(parts) == 4:
        return parts
    raise TokenError(f"invalid width arity: {section}.{key}")


def _brush(value, section, key):
    if not isinstance(value, str) or len(value) > 512:
        raise TokenError(f"invalid brush: {section}.{key}")
    pieces = PARTS.findall(value)
    if " ".join(pieces) != " ".join(value.split()):
        raise TokenError(f"invalid gradient: {section}.{key}")
    angle = 0.0
    if pieces and pieces[-1].endswith("deg"):
        angle = _finite(float(pieces.pop()[:-3]), -3600, 3600, "gradient angle")
    if not 1 <= len(pieces) <= 4:
        raise TokenError(f"gradient stops out of range: {section}.{key}")
    stops = [{"argb": _argb(piece), "offset": index / max(1, len(pieces) - 1)}
             for index, piece in enumerate(pieces)]
    return {"stops": stops, "angle_degrees": angle}


def compile_tokens(shell: dict) -> dict:
    if not isinstance(shell, dict) or len(shell) > MAX_SECTIONS:
        raise TokenError("shell section count exceeds bound")
    if sum(len(section) for section in shell.values() if isinstance(section, dict)) > MAX_KEYS:
        raise TokenError("shell token count exceeds bound")
    compiled = {}

    def resolve(section, key, chain=()):
        identity = (section, key)
        if identity in chain or len(chain) > 8:
            raise TokenError("appearance reference cycle")
        fields = shell.get(section)
        if not isinstance(fields, dict):
            raise TokenError(f"invalid appearance reference section: {section}")
        value = fields.get(key)
        if isinstance(value, str) and REFERENCE.fullmatch(value):
            next_section, next_key = value.split(".", 1)
            next_fields = shell.get(next_section)
            if not isinstance(next_fields, dict) or next_key not in next_fields:
                raise TokenError(f"missing appearance reference: {value}")
            return resolve(next_section, next_key, chain + (identity,))
        return value

    for section, fields in shell.items():
        if not isinstance(section, str) or not isinstance(fields, dict):
            raise TokenError("invalid shell section")
        output = {}
        for key in fields:
            if not isinstance(key, str):
                raise TokenError("invalid shell key")
            value = resolve(section, key)
            if value is None:
                raise TokenError(f"empty appearance token: {section}.{key}")
            if key.endswith("-alpha"):
                output[key] = {"kind": "number", "value": _finite(value, 0, 1, f"{section}.{key}")}
            elif WIDTH_KEYS.search(key):
                widths = _width(value, section, key)
                for index, side in enumerate(SIDES):
                    override = fields.get(key + "-" + side)
                    if override is not None:
                        widths[index] = _finite(override, 0, 128, f"{section}.{key}-{side}")
                output[key] = {"kind": "width", "value": widths}
            elif key.endswith(tuple("-border-width-" + side for side in SIDES)):
                output[key] = {"kind": "number", "value": _finite(value, 0, 128, f"{section}.{key}")}
            elif isinstance(value, bool):
                output[key] = {"kind": "boolean", "value": value}
            elif isinstance(value, (int, float)):
                output[key] = {"kind": "number", "value": _finite(value, -10000, 10000, f"{section}.{key}")}
            elif isinstance(value, str) and (value.startswith("#") or value.startswith("rgb") or
                                             "deg" in value or key.endswith(("-border", "-color")) or
                                             key in {"background", "text", "border", "scrim", "countdown", "accent"}):
                brush = _brush(value, section, key)
                alpha_key = key + "-alpha"
                brush["alpha"] = _finite(fields.get(alpha_key, 1.0), 0, 1, f"{section}.{alpha_key}")
                output[key] = {"kind": "brush", **brush}
            else:
                output[key] = {"kind": "raw", "value": value}
        compiled[section] = output
    return {"version": 1, "sections": compiled}
