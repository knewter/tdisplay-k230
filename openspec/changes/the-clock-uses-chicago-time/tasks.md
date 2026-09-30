## 1. Shared timezone default

- [ ] 1.1 Set the shared default and verify `nix eval --raw .#nixosConfigurations.k230-coherent-shell-hdmi-trial.config.time.timeZone` returns America/Chicago.
- [ ] 1.2 Build the profile with `nix build .#nixosConfigurations.k230-coherent-shell-hdmi-trial.config.system.build.toplevel --no-link --print-out-paths`; record its store path and localtime target (cross-build proof).

## 2. Effective device timezone

- [ ] 2.1 Install the profile and record physical console output from `python3 tools/console.py /dev/ttyACM0 --wait=3 'timedatectl show -p Timezone -p NTPSynchronized' 'date +%Z%z' 'readlink -f /run/current-system'`; confirm Chicago while retaining shell and shell-ui active. This is activation proof, not a reboot or RTC-retention test.

## 3. Land evidence

- [ ] 3.1 Validate with `openspec validate the-clock-uses-chicago-time --strict`, commit the evidence and source, merge and push, and inspect the matching Pages result.
