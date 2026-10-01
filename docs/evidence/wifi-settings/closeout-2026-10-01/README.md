# Wi-Fi Settings closeout — 2026-10-01

The operator accepts Wi-Fi Settings: “wrap it up everything but the ‘what remains’ works fine”; previously “wifi seems perfect”. This is recorded physical operator acceptance of existing setup, saved-network behavior and recovery, without inventing a fresh scan/connection/Forget/reboot sequence. No network identifier or credential is included.

The remaining password eye and keyboard reflow were independently checked on the reserved physical board with `board-eye-probe.py`, using only an invented Example network and repeated `q` characters. The fixture permits scan/status only and cannot associate or save anything. `result.json` identifies the exact installed system/client and distinguishes injected uinput contacts from a human finger. The runtime broker override was removed and the production UI restored afterward.

Reviewed native captures show masked entry, eight revealed characters, Backspace correction to seven, immediate Hide remasking, and a fresh empty masked editor after Cancel. The same wvkbd remains mapped through Show/Hide and correction; Cancel lowers it. Cancel/Connect remain wholly above the keyboard and its grip. The revealed sample is disposable public text, never a saved credential.

Source proof: `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml wifi_` and renderer secret-cache tests passed; both `handheld-shell-rust` and the coherent system closure built. The exact coherent closure in result.json was activated with `switch-to-configuration test`, and shell/seat/PipeWire services were checked. This is runtime deployment proof; final boot-profile installation is tracked in the session handoff.

Limits: screenshots are native framebuffer captures, not camera photographs. These new UI checks do not establish radio association, Internet reachability, or new reboot/Forget runs. Those existing behaviors are closed by the operator acceptance above.
