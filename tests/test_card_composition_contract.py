#!/usr/bin/env python3
"""Reject a route contract that silently loses an ownership or recovery gate."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    text = Path(sys.argv[1]).read_text()
    required = (
        "source-built, opt-in patch to pinned Sway 1.12",
        "sole DRM/KMS owner",
        "current Pixman",
        "normal `shell` service",
        "sway_container`/`sway_view",
        "normal -> deck-entry -> attached -> dragging -> selected -> expanded",
        "dismissal-requested -> refused -> restored",
        "dismissal-requested -> app-exit -> destroyed",
        "down/motion/up/cancel",
        "second contact, session lock",
        "frame callback is not panel presentation",
        "per-buffer `wlr_scene_buffer_set_dest_size`",
        "rather than a crop or saved static clone",
        "outside the\ndefault image",
    )
    absent = [item for item in required if item not in text]
    assert not absent, f"missing contract fields: {absent}"
    assert "the-handheld-has-a-coherent-ux-plan" not in text
    assert "card-feature delivery" in text
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
