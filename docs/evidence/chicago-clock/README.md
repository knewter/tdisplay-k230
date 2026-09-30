# Chicago local clock

The shared NixOS configuration selects `America/Chicago`. The configured coherent HDMI trial profile cross-builds and was activated on the physical board through the reserved serial console. `runtime.log` preserves the named observations; prompts, transfer addresses and unrelated output are omitted. `build.json` records the host commands, system path and generated localtime target; `runtime.json` records physical activation proof.

The timezone was also applied immediately with `timedatectl set-timezone America/Chicago` before deployment. Activation kept the compositor and both shell services active. The shell UI was refreshed separately so its existing libc local-time clock reads the new timezone. No kernel, renderer, input matrix, UTC clock, NTP policy or RTC policy changes are part of this change. A reboot and RTC retention were not tested.
