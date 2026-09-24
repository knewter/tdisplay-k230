# Compositor-to-Rust reveal stream: host and QEMU checkpoint

Source branch `impl/card-reveal-stream`, based on `99ac8e48cc3147a736fb7ba2366bb0cb6eb0b9d9`.
Sender revisions `ea920846ae44d602c21953b0cbb97f2289662590` and
`e185c9d7ee9314688a9dce3ffe9c5a6de0e4c4ae` implement the compositor
sender and runtime fixture. The Rust client owns
the separately developed receiver/rendering half. The existing coherent-shell
tasks 1.1, 1.2, 2.1, 4.2 and 4.4 still require integrated runtime and board
proof; no task is completed by this host check.

`SWAY_K230_CARD_REVEAL_STREAM=1` opts the touch-first card route into one
nonblocking Unix stream per bottom drawer or top shade gesture. The configured
`SWAY_K230_CARD_SURFACE_SOCKET` must equal
`$XDG_RUNTIME_DIR/k230-shell-rust.sock`; the runtime directory must be owned
and private and the socket must be owned, mode 0600. Without this flag the
fixed-argv `SWAY_K230_CARD_SURFACE_HELPER` route remains the separate rollback
behavior. The stream never forks a helper on each movement.

Each newline JSON message is at most 128 bytes with exact bounded fields:

```json
{"v":1,"kind":"reveal","surface":"drawer","phase":"update","seq":123,"progress":350}
```

`surface` is `drawer` or `shade`; `phase` is `begin`, `update`, `finish`, or
`cancel`; `seq` is unique per gesture stream. Progress is an integer 0–1000
following vertical travel, including reversal. A qualified release sends
`finish` target 1000; an early release sends target 0. The client settles from
the latest update. The compositor owns touch classification, live app/deck
pixels, and focus; the Rust client owns only its transparent overlay pixels
and local settle. Its layer can map during tracking with an empty input region;
the card adapter keeps that same layer above live cards without treating its
own reveal as a takeover. Once settled open, the normal overlay gate applies.

Writes and connection checks are nonblocking. A bounded current frame, latest
coalesced update, and terminal frame preserve begin→latest update→finish/cancel
order under backpressure; no unbounded motion queue forms. A connection or
write failure closes the stream, drains the owned contact and leaves the live
app/deck scene available. EOF after a complete terminal message is normal for
the client; EOF before it is a client-side cancel. The host test covers exact
fields, frame bounds, sequence separation, private socket rejection, and an
idle finger pause longer than the connection/write deadline.

Commands and results from the exact sender revision:

```text
python3 tests/test_card_shell_reveal.py       PASS 1 native stream/socket case
python3 tests/test_card_shell_route.py        PASS 1 fixed-helper regression case
python3 tests/test_card_shell_chrome.py       PASS 1 chrome case
python3 tests/test_card_shell_state.py        PASS 25 native policy cases
git diff --check                        PASS
nix build .#card-shell --max-jobs 1 --cores 4 --no-link --print-out-paths
                                      PASS /nix/store/13mxaxxmldpmcx418d6cq9bjvcc72ifb-k230-card-shell
CARD_SHELL_SWAY=/nix/store/6a0jd8i6sg8ix6j9mkhz72wnb4h5diyg-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway CARD_SHELL_CLIENT=/nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client python3 tests/test_card_shell_touch_first_runtime.py
                                      PASS 1 actual cross-built Sway under headless QEMU
```

The QEMU test observed three separate streams (drawer finish open, shade
finish closed after reversal, shade second-contact cancel), no per-motion
helper invocation, and an actual `k230-shell-drawer` layer painted above the
live card during tracking. The sender's built unwrapped Sway is the ELF path
above; the card package's `.sway-wrapped` is a shell script and cannot be
passed directly to `qemu-riscv64-static`. The fixture uses a native socket
collector and magenta layer fixture, not the Rust receiver. Build log:
`/tmp/k230-card-reveal-build.log`; retained local headless log:
`/tmp/k230-card-reveal-e185-qemu/sway.log`. These `/tmp` files are local
diagnostics, not committed artifacts.

Remaining gates: integrated Rust client mapping and captured pixels on begin,
intermediate movement, reversal, and settle; client disconnect,
source-unmap/privacy and keyboard ownership tests; then reserved
real-finger/panel presentation and existing frame CPU/cadence budgets.
The current QEMU test proves stream semantics and overlay stacking, not Rust
pixels, actual output presentation, physical touch, or final shell acceptance.
