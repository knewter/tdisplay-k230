# Notification row swipe: host source checkpoint

On 2026-09-24, the opt-in Rust shade gained direct, single-contact horizontal movement for a dismissible notification row. The card follows the finger within a 160-pixel bound and reveals a **Dismiss** cue. Releasing beyond 85 pixels submits dismissal for the same event ID; reversing or releasing short returns the row without action. A second contact, route change, touch cancellation, event removal, or loss of dismissibility cancels the owned gesture. Critical rows cannot start or complete a swipe even if malformed source data labels them dismissible.

Host checks from branch `impl/rust-shell-touch-gap`, based on `017125c8`:

```sh
cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --quiet
cargo clippy --offline --manifest-path nix/rust-shell-client/Cargo.toml --lib --bin k230-shell-rust -- -D warnings -A clippy::too-many-arguments -A clippy::manual-ok-err
```

The first check passed 56 library, 6 binary, 10 appearance, 5 background, and 8 service tests. The second passed with allowances for existing broad rendering argument counts and two pre-existing manual-`ok` matches in theme preview code; strict Clippy without the latter allowance reports those two unrelated matches. Unit coverage includes reversal and event-identity rejection; the renderer test checks pixel movement, return to the original frame, and fixed critical rows. The current `tests/test_notification_center.py --case swipe-cancel --case swipe-dismiss --case critical-retained` explicitly reports those UI cases unimplemented, so this source checkpoint **does not complete** task 3.3. It does not prove animation cadence, kinetic scroll/tap-to-stop, QEMU compositor pixels, or physical touch.
