# Live Home page-driver closeout

2026-10-01, paired Sway/Rust under qemu-riscv64-static. [result.json](result.json) records PASS for held-contact repeat edge turns, last-edge creation of a new page, dropping onto the visible new page, and an interior fling which never reached the edge band. Persisted page contents, rather than screenshot differences, are the authoritative drop checks.

Native compositor captures show the edge affordance, created page/drop, Bubble and Thin clock styles, and an explicitly started Analog/Dot matrix/Weather runtime layout. Weather is unavailable in the host namespace; no host picture is claimed as live-board weather. A previous full run timed out on an unrelated dock-folder step; the narrow run exercises only this proposal's gates and is the successful evidence.

```sh
unshare -Ur python3 tests/rust_home_screen_qemu.py --fluid-only \
  --sway "$SWAY/bin/sway" --swaymsg "$SWAY/bin/swaymsg" \
  --rust "$RUST/bin/k230-shell-rust" --theme-bundle "$THEMES" \
  --icons "$ICONS" --output NEW_OUTPUT_DIRECTORY
```

Exact store paths and themes are recorded in the result. This proves actual input/compositor/runtime wiring under emulation. It does not establish real-finger feel, daylight contrast, a present battery, or physical panel behavior; board follow-on evidence is separate.
