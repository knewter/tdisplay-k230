## 1. Display conversion

- [ ] 1.1 Add Fahrenheit formatting for all Home weather temperatures without changing cache fields; cross-build `nix build .#nixosConfigurations.k230-coherent-shell-hdmi-trial.config.system.build.toplevel --no-link --print-out-paths`.

## 2. Board verification

- [ ] 2.1 Install that profile and verify the running Rust binary and active shell services with `python3 tools/console.py /dev/ttyACM0 --wait=3`; capture Home using board-native grim and inspect the weather temperatures. Commit only reviewed, cropped widget evidence without private location or unrelated screen content. This is rendered board capture, not finger or reboot proof.

## 3. Integration

- [ ] 3.1 Run `openspec validate the-weather-widget-shows-fahrenheit --strict`, commit the source/evidence, merge and push master, and inspect the matching Pages deployment.
