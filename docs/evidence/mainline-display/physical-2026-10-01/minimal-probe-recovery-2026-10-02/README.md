# Recovery after the minimal initrd diagnostic

The operator reported `done` after the requested power cycle. The coordinator
reserved the board and serial console, waited for normal boot to finish, then
observed a fresh Linux root prompt before sending the protected check.

At 2026-10-02T14:42:56.872178+00:00, the unchanged checker passed against the committed
normal-boot identities and all eight protected boot-file hashes. Its helper
SHA-256 is `86bcf6f2c175d44d27f68015a9cc5a1ad7731ad50b6bbf3347859a4840cc7df7`, from source
`86cc840cd7602f437b220e72dd80ee52f27ef69d`. [postflight.json](postflight.json) records Linux
6.6.36, the matching normal system/profile/kernel and init selector, three
active shell services, and fresh boot ID `64898774-34da-4206-afc6-34508a03258d`.
The previous normal boot ID was `e7cf8096-44a0-4bdf-815d-2f1aec4126fb`; a changed ID
was mandatory. The baseline is the committed ordinary-boot postboot report,
with that previous ID supplied by the preceding corrected-probe recovery.

The helper and expected identities were streamed only into `/run` over an
exclusive 115200-baud `/dev/ttyACM0` session with `/tmp/k230-board.lock` held.
Exact board command, with a fresh UUID substituted for the token:

```sh
/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 -I /run/k230-mainline-normal-state.py postflight FRESH_32_HEX_TOKEN
```

Only a complete standalone marker for the fresh token was accepted. Raw UART
captures remain private outside Git. This check changed no persistent boot
selection, profile, firmware or protected boot file.

Home was requested through compositor IPC (`output * dpms on` and
`card_shell home`), then transient surfaces were hidden with the exact
installed Rust executable `3hy6h165…/bin/k230-shell-rust --surface hide`.
[output-state.json](output-state.json) records the powered DSI-1 output at
568×1232, 52.190 Hz, transform normal. [home.png](home.png) is a new,
visually reviewed native `grim` capture. It shows the installed normal shell,
icons, saved wallpaper and clock. There is no new camera or real-finger test.

This independently proves normal recovery after the
[failed minimal run](../minimal-probe-2026-10-02/README.md); it does not turn
that diagnostic into a pass. The later proc-setup correction has not been run
on the board. Mainline root access, touch and restart proof remain open.
