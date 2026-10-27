# GTK app chrome reaches the touch floor: board evidence

Change: `gtk-app-chrome-reaches-the-touch-floor`. Evidence class: board,
native `grim` capture, with Files started by an injected tap on its Home dock
icon. Build: `/nix/store/dhmp8mdiii13xynd0cqyhjr5mkad0mah-nixos-system-nixos-26.11.20260919.20b1ddd`,
test-activated, 2026-10-27 ~03:36Z.

- `board/files-landscape.png`: Files (GTK4) about 20 s after launch. The
  window fills the 1232x568 output without overflowing. Measured from the
  capture's pixel runs: the path-bar button is 88 px tall (y 14-101) and a
  sidebar row is 84 px (y 106-189), above the 64 px floor.
