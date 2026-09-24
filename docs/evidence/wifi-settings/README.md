# Wi-Fi Settings evidence

The protected broker host checkpoint was tested from source commit `924690e8` plus the one-line flake output added in the following commit. On 2026-09-24 UTC:

- `python3 -m unittest tests.test_wifi_settings_broker -v` — ten synthetic host cases passed after the bounded multi-network correction. Names and passwords in those fixtures are invented; the test neither uses a radio nor reads the board.
- `tools/test-k230-wifi-persistent-service.sh` — passed after correcting its stale documentation-string check; the pre-existing `LoadCredential` unit values remain intact.
- `nix build --no-link --print-out-paths --max-jobs 1 --cores 4 .#wifi-settings-broker` — passed for the corrected multi-network source; derivation `/nix/store/fcbhbqdgq4bh5y9a6i2dm7anqd0fhpq0-k230-wifi-settings-broker.drv`, package `/nix/store/1x04vqngky553b2ww2p65p8j630mprnv-k230-wifi-settings-broker`. The earlier single-network checkpoint produced `/nix/store/5l60c5apxyqiia6391xvwmqjpkagr0bc-k230-wifi-settings-broker` and is superseded.
- `openspec validate the-handheld-configures-wifi-from-settings --strict` — passed.

This is source, host-test, Nix evaluation and package build proof only. The broker has not run on the board. Real scan, association, protected persistence, recovery timer, reboot reconnect, Forget and Settings touch/keyboard behavior remain **UNVERIFIED**.
