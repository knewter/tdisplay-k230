# Wi-Fi Settings evidence

The protected broker host checkpoint was tested from source commit `924690e8` plus the one-line flake output added in the following commit. On 2026-09-24 UTC:

- `python3 -m unittest tests.test_wifi_settings_broker -v` — eleven synthetic host cases passed after the bounded multi-network, real-format scan and cancellation corrections. Names and passwords in those fixtures are invented; the test neither uses a radio nor reads the board. The `* Authentication suites:` fixture matches [upstream `iw` v6.9 `scan.c`](https://kernel.googlesource.com/pub/scm/linux/kernel/git/jberg/iw/+/refs/tags/v6.9/scan.c), which prints the `\t * ` prefix.
- `tools/test-k230-wifi-persistent-service.sh` — passed after correcting its stale documentation-string check; the pre-existing `LoadCredential` unit values remain intact.
- `nix build --no-link --print-out-paths --max-jobs 1 --cores 4 .#wifi-settings-broker` — passed for the multi-network source before the final scan/cancellation response correction; derivation `/nix/store/fcbhbqdgq4bh5y9a6i2dm7anqd0fhpq0-k230-wifi-settings-broker.drv`, package `/nix/store/1x04vqngky553b2ww2p65p8j630mprnv-k230-wifi-settings-broker`. This package identity is superseded by the later source and must not be used as exact proof of it.
- `openspec validate the-handheld-configures-wifi-from-settings --strict` — passed.

This is source, host-test, Nix evaluation and package build proof only. The broker has not run on the board. Real scan, association, protected persistence, recovery timer, reboot reconnect, Forget and Settings touch/keyboard behavior remain **UNVERIFIED**.
