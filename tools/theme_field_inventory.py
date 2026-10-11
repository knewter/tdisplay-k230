"""Inventory every active field in the pinned Omarchy shell template.

The inventory is intentionally conservative: an upstream field that has no
current handheld owner is reported as unavailable, and new sections/roles
must be classified before this check passes.
"""

from pathlib import Path
import hashlib
import tomllib


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "nix/omarchy-theme-tools/upstream/default/themed/shell.toml.tpl"


def field_status(section: str, key: str) -> tuple[str, str] | None:
    """Return (status, current owner) for one generated-template field."""
    unavailable_section = {
        "bar": ({"background", "background-alpha", "text", "active", "scale-with-font", "size-horizontal", "size-vertical"}, "No persistent bar surface exists."),
        "popups": ({"background", "background-alpha", "text", "border", "border-alpha"}, "No standalone popup renderer consumes this section."),
        "tooltip": ({"background", "background-alpha", "text", "border", "border-alpha"}, "The handheld has no hover-tooltip surface."),
        "polkit": ({"background", "background-alpha", "text", "text-error", "border", "border-error", "border-alpha", "scrim", "scrim-alpha", "accent"}, "No in-shell polkit prompt is shipped."),
        "lock": ({"background", "background-alpha", "text", "placeholder", "text-error", "border", "border-active", "border-error", "border-alpha", "selection", "selection-alpha"}, "The image has no shell-owned lock surface."),
        "hyprland": ({"active-border", "active-border-foreground"}, "Hyprland is not the handheld compositor; these tokens are retained only."),
    }
    if section in unavailable_section:
        keys, reason = unavailable_section[section]
        if key in keys:
            return "unavailable", reason
        return None
    if section == "controls":
        applied = {"normal-fill-alpha", "selected-color", "selected-fill-alpha",
                   "selected-border", "selected-border-width", "selected-border-alpha",
                   "pressed-fill-alpha", "hover-cursor-color", "hover-cursor-fill-alpha",
                   "hover-cursor-border", "hover-cursor-border-width", "hover-cursor-border-alpha",
                   "focus-color", "focus-fill-alpha", "focus-border", "focus-border-width", "focus-border-alpha"}
        adapted = {"normal-color"}
        unavailable = {
            "normal-border": "Ordinary row rims are deliberately omitted.",
            "normal-border-width": "Ordinary row rims are deliberately omitted.",
            "normal-border-alpha": "Ordinary row rims are deliberately omitted.",
            "selection-fill-alpha": "Text-selection paint belongs to the input client, not these cards.",
        }
        if key in applied:
            owner = "Rust Home icon/folder transient press uses this fill without persistent selection." if key == "pressed-fill-alpha" else "Rust control-card renderer; state outlines retain gradients, alpha and per-side widths."
            if key.startswith("hover-cursor-"):
                owner = "Mouse hover on existing Home/drawer/control chrome; it never activates a control."
            if key.startswith("focus-"):
                owner = "Existing drawer search, Wi-Fi password and folder-rename fields own focused chrome."
            return "applied", owner
        if key in adapted:
            return "adapted", "Rust Settings labels use the first color stop; fills retain full brushes."
        if key in unavailable:
            return "unavailable", unavailable[key]
        return None
    if section == "font":
        if key == "base-size":
            return "adapted", "Rust shell labels and C deck headers scale by base-size/12, bounded to 0.8–1.25; Settings role overrides retain 11–24px bounds."
        return None
    if section == "spacing":
        if key == "scale":
            return "adapted", "Shared visual text insets, Home/drawer label gaps, widget padding and C header icon gaps scale within 0.8–1.25; Settings padding is 12–36px. Hit/panel geometry stays fixed."
        if key == "scale-with-font":
            return "adapted", "When true (default), visual spacing multiplies scale by base-size/12 before the handheld bounds; false decouples font and spacing."
        return None
    if section == "notifications":
        statuses = {
            "background": ("applied", "Rust Shade panel background brush."),
            "background-alpha": ("applied", "Compiled into the Shade background brush alpha."),
            "text": ("adapted", "Rust Shade uses the first brush stop for solid glyph color."),
            "countdown": ("adapted", "Rust Shade uses the first brush stop for its progress indicator."),
            "border": ("unavailable", "The Shade does not paint a notification outline."),
            "border-alpha": ("unavailable", "The Shade does not paint a notification outline."),
        }
        return statuses.get(key)
    if section == "launcher":
        statuses = {
            "background": ("applied", "Rust Home and drawer surface background brush."),
            "background-alpha": ("applied", "Compiled into consumed Home/drawer background brushes."),
            "text": ("adapted", "Rust Home/drawer glyphs use the first brush stop."),
            "border": ("unavailable", "Home/drawer surfaces do not paint ordinary outlines."),
            "border-alpha": ("unavailable", "Home/drawer surfaces do not paint ordinary outlines."),
            "scrim": ("applied", "Home folder and widget-picker scrim brush."),
            "scrim-alpha": ("applied", "Home folder and widget-picker scrim brush."),
            "selected-background": ("unavailable", "No persistent selected Home card is painted."),
            "selected-background-alpha": ("unavailable", "No persistent selected Home card is painted."),
            "selected-text": ("adapted", "Rust Home/drawer accent glyphs use the first brush stop."),
            "selected-border": ("unavailable", "No persistent selected Home card is painted."),
            "selected-border-alpha": ("unavailable", "No persistent selected Home card is painted."),
        }
        return statuses.get(key)
    if section == "menu":
        statuses = {
            "background": ("applied", "Rust app-actions menu background brush and Settings fallback."),
            "background-alpha": ("applied", "Compiled into the consumed menu background brush."),
            "text": ("adapted", "Rust app-actions glyphs use the first brush stop."),
            "border": ("unavailable", "App-actions menu does not paint an ordinary outline."),
            "border-alpha": ("unavailable", "App-actions menu does not paint an ordinary outline."),
            "scrim": ("applied", "App-actions overlay scrim brush."),
            "scrim-alpha": ("applied", "Compiled into the app-actions scrim brush."),
            "selected-background": ("unavailable", "No selected app-action card is painted."),
            "selected-background-alpha": ("unavailable", "No selected app-action card is painted."),
            "selected-text": ("adapted", "Rust app-actions accent glyphs use the first brush stop."),
            "selected-border": ("unavailable", "No selected app-action card is painted."),
            "selected-border-alpha": ("unavailable", "No selected app-action card is painted."),
        }
        return statuses.get(key)
    if section == "image-picker":
        statuses = {
            "scrim": ("applied", "Chooser slice dimming consumes the image-picker scrim brush."),
            "scrim-alpha": ("adapted", "Authored scrim alpha is multiplied by the existing per-slice blend; a centered slice is undimmed."),
            "text": ("adapted", "Chooser glyphs use the first brush stop."),
            "selected-border": ("unavailable", "Chooser carousel does not paint selection outlines."),
            "selected-border-alpha": ("unavailable", "Chooser carousel does not paint selection outlines."),
            "unselected-border": ("unavailable", "Chooser carousel does not paint slice outlines."),
            "unselected-border-alpha": ("unavailable", "Chooser carousel does not paint slice outlines."),
        }
        return statuses.get(key)
    return None


def inventory(template: Path = TEMPLATE) -> list[dict[str, str]]:
    fields = tomllib.loads(template.read_text())
    rows = []
    for section, roles in fields.items():
        for key in roles:
            classified = field_status(section, key)
            if classified is None:
                rows.append({"field": f"{section}.{key}", "status": "unknown",
                             "owner": "No explicit compatibility classification yet."})
                continue
            status, owner = classified
            rows.append({"field": f"{section}.{key}", "status": status, "owner": owner})
    return rows


def render_markdown(template: Path = TEMPLATE) -> str:
    rows = inventory(template)
    parsed = tomllib.loads(template.read_text())
    digest = hashlib.sha256(template.read_bytes()).hexdigest()
    lines = [
        "# Generated Omarchy shell-field inventory",
        "",
        "Host source audit; this is not panel or touch acceptance. The source is",
        "the checked-in pinned upstream template `nix/omarchy-theme-tools/upstream/default/themed/shell.toml.tpl`.",
        "Upstream revision: `omacom/omarchy@28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`.",
        f"Template SHA-256: `{digest}`.",
        f"It contains {len(rows)} active fields across {len(parsed)} sections. Every active field appears below.",
        "Commented example overrides are not active fields; themes may still add them and they remain preserved.",
        "",
        "| Generated field | Classification | Current owner / adaptation |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| `{row['field']}` | {row['status']} | {row['owner']} |" for row in rows)
    lines.extend([
        "",
        "The test `python3 tests/test_handheld_theme_rendering.py` checks that the",
        "inventory covers every active key and has no unknown classifications.",
        "Renderer unit tests verify the actual Rust Cairo/Pango path for the",
        "hover/focus state, bounded font/spacing adaptation and Home's momentary pressed fill.",
        "Idle outlines, text selection and absent surfaces are explicitly unavailable; they",
        "are not new surfaces or interaction modes introduced by appearance import.",
        "New physical recordings and numerical measurements are waived by the operator;",
        "specific unobserved glass/boot cases and unmeasured costs remain UNVERIFIED.",
        "",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    print(render_markdown(), end="")
