# Settings and notification theme coverage: host proof

2026-10-01, x86_64 host. This is real Rust/Cairo renderer and helper/parser
proof, not Wayland presentation, physical touch, native panel capture or boot.

The rendered owners are Rust `Route::Settings` and `Route::Shade`; the Nix
Settings/notification helpers only supply data/actions. Both surfaces already
share startup appearance and the Rust/deck transaction's commit/rollback owner.
No extra endpoint or replacement Settings app was added.

Corrected paint gaps: Settings normal text consumes `controls.normal-color`,
selected rows use `selected-color` (normal fallback), and selected outlines honor
zero/per-side authored widths. Ordinary outlines remain omitted. New reports
name every controls/notifications token as applied, adapted, unavailable or
unknown; absent hover/focus and ordinary outlines are unavailable, not implied
covered. Solid text uses the first brush stop, reported as adaptation. Existing
immutable reports without the added category remain readable.

Commands, run in the pinned native Nix environment with Cargo target under
`/home/jadams/tmp/k230-settings-native-target`:

```sh
python3 tests/test_handheld_theme_rendering.py --surface system
cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml
cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --test system_theme_compatibility
python3 -m unittest tests.test_handheld_theme_rendering tests.test_omarchy_theme_activation tests.test_theme_catalog tests.test_omarchy_theme_transaction
python3 tools/blob-scan.py
```

Results: named system test PASS (six Python checks plus two actual renderer
pixel tests, required to execute); full Rust suite PASS (422 library checks,
one ignored timing benchmark, 64 binary/integration checks); additional typed
compatibility parser regression PASS; Python generation/catalog/transaction
suite PASS (68 checks); blob scan PASS. The role test mutates every claimed
required color/fill/outline role and checks painted pixels, verifies selected
color does not alter a normal row, and exercises the actual Settings/Shade
route renderer. The swap/rollback test verifies byte-identical restored frames.
The parser regression preserves adapted roles, rejects oversized entries and
accepts old reports without the category. The system test fails if Cargo or
the two renderer checks cannot run; it cannot silently succeed with zero tests.

Native dependencies came from `nixosConfigurations.k230.pkgs.buildPackages`
at `656bcf2c38a545f34ab81098526a0075c88c2ed3`, with Cairo, Pango, librsvg,
GLib, libxkbcommon, cargo/rustc/pkg-config. Tests ran on this worktree's changed
source; the cross-built candidate's exact committed source/closure and physical
proof remain separate records.

An attempted legacy standalone `theme_catalog_bridge_host` check could not
compile because its pre-existing shim lacks the runtime_trace module. No repair
of that unrelated harness was included; the same new parser regression runs
against the actual Rust shell library above. No unperformed command is ticked.

A later native board trial at `eb38af2a` showed that Settings and Shade
repainted on rollback, while the separate Home dock layer retained its light
frame. Shared appearance adoption now also marks Home dirty for optimistic
preview adoption, ordinary commit/rollback, and failed-commit restoration.
The binary/route suite re-ran after this correction: 22 checks PASS. This
checkpoint still requires an exact rebuilt candidate and fresh board proof;
the earlier captures cannot establish the correction.
