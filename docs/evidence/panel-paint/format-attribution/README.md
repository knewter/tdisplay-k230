# Remaining draw identities — 2026-10-20 UTC

Diagnostic source `0eae9900f2bebdc579ad5a8671148e3939ca12c5` built successfully
and temporarily ran as system
`/nix/store/v00g9mmdy721akia8d6vh4h49x7wxjva-nixos-system-nixos-26.11.20260919.20b1ddd`.
The exact build command/result and observed system identity are adjacent.
Baseline boot/profile remained selected; no reboot. CI39344786342 succeeded.

The three-gesture run has both512/128 trace caps reached and only12 complete
gesture-window passes. Texture mean7.144ms; no budget pass is claimed. The
new numeric fields prove that the699,776-pixel draw is **ARGB8888→RGB565,
unscaled, no extra mask, OVER**, source1232×568, mean2.335ms across14 selected
rows. It is not the XRGB card path. The313,208-pixel card averages1.501ms.
Other ARGB draws include title/header geometry with real transparency.
Source lookup identifies the full-panel wallpaper owner as the Rust client.

The collector's first normalization mistakenly removed source dimensions
from rotation rows as well as from the separate draw detail payload. The
strict parser rejected that output. It was corrected and the original journal
was re-read for the **same recorded PID53942**; all640 original numeric rows
were normalized again. No geometry or environment value was inferred or
fabricated. The accepted profile contains all rotation dimensions. The
corrected collector source and full512 draw detail rows are adjacent.

```sh
python3 tools/panel-paint-profile.py --log docs/evidence/panel-paint/format-attribution/profile.log --workload docs/evidence/panel-paint/format-attribution/workload.json --output docs/evidence/panel-paint/format-attribution/profile.json
```

A direct partial-alpha implementation passed512 Pixman alpha-oracle cases,
but dense-alpha synthetic copies regressed3.5×; it was rejected rather than
enabling it for these images. See ../rejected-alpha/README.md. CompilerO3
unrolling also regressed the actual RGB565 rotation (../rejected-rotation/).

The next bounded source correction certifies **each completed wallpaper
frame's actual alpha bytes**, publishes a full opaque region only for all255,
and clears it on any transparency or region allocation failure. Buffer pool,
pixels, input region, damage, callback and attachment ownership are retained.
This applies equally to default/still/video frames; no video-alpha assumption.
The renderer can then use exact ARGB SRC→RGB565 conversion, while ARGB OVER
and masks keep Pixman. Native768 cases (including every alpha value underSRC),
Rust opacity transitions and the Rust binary check pass. The focused Rust
commands/logs are adjacent; cross-build and board proof remain required.

```sh
CARGO_TARGET_DIR=/tmp/k230-panel-paint-cargo-target cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked --lib frame_opacity_tests -- --nocapture
CARGO_TARGET_DIR=/tmp/k230-panel-paint-cargo-target cargo check --manifest-path nix/rust-shell-client/Cargo.toml --locked --bin k230-shell-rust
```

After profiling, own92 override and600s rollback timer were removed, baseline48af
restored, normal/Home/services/no test devices verified, and the board released.
No camera recording or persistent candidate selection; hardware gates remain open.
