# Drawer search with the standard keyboard

Source `3e22a36e34ee38ff0171b48f884c52108a2db94f`, 30 September 2026. Search now uses the shared wvkbd process instead of a custom keypad. The field paints a themed focus outline and an insertion caret, accepts normal Wayland keyboard events, and reserves the keyboard plus gesture grip above the app grid. Enter/Escape hide the keyboard while retaining the filter; tapping Search reopens it. Leaving the drawer clears the filter and releases keyboard focus.

## Paired QEMU proof

[Exact result and binary identities](result.json). The actual RISC-V Rust shell, Sway and wvkbd ran under user-mode QEMU. A native Wayland probe application and a virtual-keyboard client provide controlled app/key observations. Forty-eight synthetic desktop entries keep the test independent of private apps or data.

```sh
python3 tests/rust_drawer_keyboard_qemu.py \
  --sway /nix/store/dsn90m4lcn1mbziy52v1y7a98vdramn4-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/z3ld6xwy5ipcyhnswns1djggmjkrqw9h-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --keyboard /nix/store/f78wgpdcniq2v2yn274dd0yi29gh9sc6-wvkbd-riscv64-unknown-linux-gnu-0.20/bin/wvkbd-mobintl \
  --client <native probe compiled from nix/card-composition-probe-client/card-composition-probe-client.c> \
  --output <fresh private directory>
```

PASS: focus, text/filtering, correction by an actual wvkbd Backspace touch, drawer preservation, Enter and Escape dismissal, immediate reopen, desktop-entry launch, overlay removal and a key delivered to the launched app. Pixel comparison against an independently injected Backspace result avoids OCR ambiguity between `00` and `0`. This regression also caught and fixed a late focus-loss event canceling a new focus request.

[Unfocused field](search-unfocused.png), [focused field and normal keyboard](search-focused.png), [typed query](search-typed.png), [actual keyboard correction](search-corrected.png), [keyboard dismissed](search-keyboard-dismissed.png), [launched app with restored focus](app-focus-restored.png).

## Host checks and limits

`cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml`: 472 passed, one pre-existing ignored test. The stale Home-handle fixture was corrected separately on master `baf29a5c`; no pixel check was disabled. QEMU uses a 420px keyboard with a 56px grip; the board configuration uses its configured 400px height. Runtime input and render geometry share that reservation.

These are headless captures and injected events, not real-finger acceptance, panel proof or board frame timings. The field currently supports appending text, Backspace and Enter/Escape; this work does not claim a general text widget with selection, clipboard operations or arbitrary caret movement. Hardware acceptance remains task 6.3; the independent frame-budget gates 5.2/5.4 remain open.

The source revision above also passed `flock -n /tmp/k230-nix-build.lock nix build .#handheld-shell-rust .#nixosConfigurations.k230-coherent-shell-hdmi-trial.config.system.build.toplevel --no-link --print-out-paths --max-jobs 2 --cores 8`. Standalone shell: `/nix/store/xdg66yi147v7wdqpqsc5gx2hvk6s1gca-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`. Matching system: `/nix/store/y4nvdka66kp6qxb9bkls8r3r5caf19iw-nixos-system-nixos-26.11.20260919.20b1ddd`; its actual Rust executable is the `z3ld6xwy…` binary exercised above.
