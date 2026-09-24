# Supervised keyboard and handle contrast checkpoint

The optional coherent shell now starts wvkbd through a `shell-keyboard`
systemd unit bound to `shell.service`. Its bounded wrapper waits for exactly
one owned Wayland socket and executes the unchanged wvkbd binary with the
configured 420 px height and `--hidden`. `Restart=always`, a three-second
delay, and disabled systemd start-rate latching recover a keyboard that exits
after temporary or prolonged output loss without a rapid retry loop. The coherent
Sway config no longer starts a duplicate keyboard. The noncoherent Sway path
keeps its original keyboard command.

The trigger was an actual headless QEMU output-disable run: wvkbd exited with
`Could not find config for output HEADLESS-1`; Sway returned the live app to
full 1232 px height. An explicit keyboard restart after output re-enable
restored two-finger show, grip hide and ordinary key delivery
([native result](native-qemu/output-restart-result.json)). This tests the
compositor and restarted client; it does not pretend QEMU ran the NixOS
systemd unit. Unit graph evaluation and an exact image build are separate
checks below.

The authored foreground role now paints the grip line instead of the selected
card fill. For the pinned Catppuccin dark palette, foreground `#cdd6f4`
against card `#161622` has a 12.39:1 contrast ratio, compared with 1.43:1
for selected fill `#313244`. For the pinned bundled Latte colors, foreground
`#4c4f69` against card `#e3e4e8` has 6.29:1, compared with 1.04:1 for
selected fill `#dce0e8`. Ratios use the standard linear-sRGB relative
luminance formula. Inputs were the checked-in
`nix/handheld-theme-default/catppuccin/colors.toml` and
`/nix/store/aajw0dknkkwx4mdswaa0vd52li64d6i7-handheld-theme-default-28ceaae7/share/omarchy/themes/catppuccin-latte/colors.toml`.

The exact source/build and dark/light rendered-pixel checks are recorded below
when available. Installed output loss and physical handle legibility remain
unverified.
