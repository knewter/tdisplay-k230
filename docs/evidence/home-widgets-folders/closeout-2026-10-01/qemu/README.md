# Folder and widget paired-compositor closeout

2026-10-01, host paired Sway/Rust under qemu-riscv64-static. This is injected touch and a real Wayland virtual-keyboard connection, not physical finger input. All 31 checks in [result.json](result.json) passed. Native compositor captures above are unedited.

Source: folder-focus fix 299cb7e7, landed as 63b13bb2. The old rename timeout was a real focus error: Sway grants exclusive layer keyboard focus only on Top/Overlay, while Home normally uses Bottom. Home now rises temporarily for editing and returns afterward. The harness also supplies seat keyboard capability before requesting focus, deletes the existing name before typing, and restores a second page after a dock move prunes it.

The run proves drawer placement, folder creation/open/rename/member launch, dragging a member out and dissolving the remaining one-member folder, dock folders, widget-picker placement and persisted state across process restart. Native captures do not establish physical feel, battery presence or daylight contrast. The physical follow-on is separate.

Command (exact paths are in the result):

```sh
unshare -Ur python3 tests/rust_home_screen_qemu.py \
  --sway "$SWAY/bin/sway" --swaymsg "$SWAY/bin/swaymsg" \
  --rust "$RUST/bin/k230-shell-rust" --theme-bundle "$THEMES" \
  --icons "$ICONS" --output NEW_OUTPUT_DIRECTORY
```

The initially failed full runs are not counted as successful proof.
