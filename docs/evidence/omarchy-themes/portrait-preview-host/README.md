# Portrait wallpaper preview: host checkpoint

Source base: `017125c89a1103c0371035f95544a801f41c14e0`; candidate: this evidence commit. The chooser previously decoded a 512×176 center crop for a 568px-wide screen, while the persistent wallpaper decoded a 568×1232 crop. A landscape still could therefore preview a different part of the source than the user would see after Apply. The chooser now requests the same bounded output geometry and scales that portrait frame into the preview panel. Only selected stills are decoded; generation changes and cancellation still discard stale replies.

The [host capture](preview.png) uses a public synthetic red/blue 80×160 source. Both vertical regions remain visible in the small screen sample. The worker pixel test checks the first and last Cairo pixels after portrait cropping, while the renderer test checks the 568×1232 request and produces the capture. Commands:

```sh
cargo fmt --manifest-path nix/rust-shell-client/Cargo.toml --check
cargo test --manifest-path nix/rust-shell-client/Cargo.toml --offline --locked
K230_THEME_FIXTURE_PNG=/tmp/k230-theme-output-crop-preview.png cargo test --manifest-path nix/rust-shell-client/Cargo.toml --offline --locked theme_list_preview_and_scroll_paint_distinct_handheld_scenes -- --nocapture
python3 tools/blob-scan.py
```

These are host pixels, not a QEMU or panel capture. Still decode, fit/center options, video backgrounds, and physical theme interaction remain under the open theme tasks; this checkpoint does not close tasks 4.1 or 4.2.
