# Edge control intent and Home return: host proof

An edge down now holds a weak target until motion distinguishes a gesture from a tap. A tap sends balanced input to the original live target; an actual edge drag replays the original origin/time into existing native motion policy. Extra contacts cancel a forwarded client stream rather than turn cancellation into a tap. Output/seat loss and keyboard chord takeover clear pending ownership. Real wvkbd keys keep their full input surface. Home paints a themed bottom handle: a stationary tap returns to the retained cards, while an upward drag still opens the app drawer.

Exact matching [build identities and source hashes](build.json) accompany [touch-first protocol results](touch-first-result.json), [legacy routing results](legacy-result.json) and [mouse/Home regression output](pointer-test.txt).

```sh
flock /tmp/k230-nix-build.lock nix build .#nixosConfigurations.k230-coherent-shell-hdmi-trial.config.system.build.toplevel --no-link --print-out-paths --max-jobs 2 --cores 8
python3 tests/test_card_touch_routing.py --edge-intent --sway <build.json sway> --output <fresh-private-directory>
python3 tests/test_card_touch_routing.py --sway <build.json sway> --output <fresh-private-directory>
CARD_SHELL_SWAY=<build.json sway> CARD_SHELL_CLIENT=<native-probe-client> python3 -m unittest discover -s tests -p test_card_shell_pointer_navigation.py -v
```

The native probe client was compiled from `nix/card-composition-probe-client/card-composition-probe-client.c` with the pinned fixture's xdg-shell generated protocol and host Wayland headers, `cc -std=c11 -O2 -Wall -Wextra -Werror`. Tests ran the actual cross-built Sway under `qemu-riscv64-static`. Eight touch-first cases, seven legacy cases and the mouse navigation regression passed. The overlay/keyboard test clients implement their actual layer namespaces but are protocol fixtures; these results do not establish actual Rust search Backspace semantics or physical feel. After keyboard removal the harness waits 200 ms for the test app to commit its restored buffer; the compositor correctly refuses an unpainted resized source rather than displaying it as a card.

An initial build used a nonexistent Sway `geo` member and was corrected to use actual scene-node coordinates and current surface dimensions before the passing build. The first host mouse invocation lacked a built native probe client; the recorded invocation uses the freshly compiled source fixture. No failed result was relabeled a pass.

Deployment and board-injected header/search-key checks are task 4.2; real-glass controls and navigation remain task 4.3. No kernel or device tree changes are part of this fix.

## Home fixture reconciliation, 30 September 2026

The full Rust suite on unchanged master `7515378f` failed the Home portrait pixel-identity test: the earlier Home-handle implementation intentionally added a 96×6 bottom pill but left its committed render fixture stale. Rendering unchanged master source through `render_responsive_evidence` and comparing RGBA pixels shows the sole difference is `(236,1218)..(332,1224)`, the handle's intended rectangle. The portrait Home fixture is refreshed to that visually inspected render; no renderer source changes in this correction. This is host pixel evidence, distinct from the operator's new real-glass report that tapping Home's bottom handle opened overview correctly. Compact search Backspace still closes the drawer according to the same operator: that negative physical result remains open in the app-drawer standard-keyboard follow-up.
