# Rust theme catalog bridge: standalone host checkpoint

Observed 2026-09-24 on branch `impl/rust-theme-catalog-bridge`, base
`origin/master` `1df7b5df`. This source adds an unlinked Rust backend module;
the touch chooser and renderer do not yet call it. It follows the installed
`k230-theme` JSON contract: list, preview by opaque theme ID, optional
background choice by preview ID, then activate only with the exact reviewed
generation. Preview has no activation side effect. The installed wrapper,
not the Rust module, owns the paired Sway/Rust transaction and source
preparation.

`ThemeWorker::try_submit` and `try_recv` keep process I/O off the Wayland
thread. The worker invokes one configured absolute executable directly with
validated 24-character lowercase IDs, a four-request queue, a 20-second
process deadline, 1 MiB response cap and 8 KiB error cap. It kills the
process group on timeout/overflow and parses typed schema-1 results. The
frontend receives separate shell activation and post-ACK app-sync status;
an app-sync failure is not mislabeled as a failed shell transaction. Returned
background paths must remain under the staged generation's backgrounds
directory. The module does not decode previews or run theme-provided files.

```sh
cargo fmt --manifest-path tests/theme_catalog_bridge_host/Cargo.toml --check
cargo test --offline --manifest-path tests/theme_catalog_bridge_host/Cargo.toml --locked
cargo clippy --offline --manifest-path tests/theme_catalog_bridge_host/Cargo.toml --locked --all-targets -- -D warnings
python3 tests/test_theme_catalog.py
git diff --check
```

PASS: four focused Rust tests, including exact argv/background choice,
nonblocking submission, invalid shell-text ID refusal, stale generation and
path rejection, bounded large output, typed app-sync failure and useful
nonzero JSON error; nine existing Python catalog tests passed. This is host
module proof only. Frontend integration, touch preview/cancel/apply, target
build, image boot, panel readability and real-finger evidence remain open.
