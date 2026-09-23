#!/usr/bin/env python3
"""Host structural gates for the intentionally opt-in Sway probe package."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    mode = sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv else None
    assert mode == "selected", "only the selected Sway route has a host checkpoint"
    package = (ROOT / "nix/card-composition-probe.nix").read_text()
    patch = (ROOT / "nix/patches/sway-k230-card-composition-probe.patch").read_text()
    flake = (ROOT / "flake.nix").read_text()
    shell = (ROOT / "nix/shell.nix").read_text()
    for required in ("swayUnwrapped", "sway-unwrapped = patchedUnwrapped",
                     "--describe", "--sway", "starts no compositor"):
        assert required in package, required
    assert "SWAY_K230_CARD_COMPOSITION_PROBE" in patch
    assert "live_scale=UNVERIFIED" in patch
    assert "/dev/dri" not in package + patch
    assert "card-composition-probe =" in flake
    assert "card-composition-probe" not in shell
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
