# Verified handheld checkpoint, 2026-09-22

The daily image is documented in [daily-shell-image.md](daily-shell-image.md).
It was written over USB UMS, reset into the source-built boot chain, and checked
on the physical board with an initially empty shell home. No full image readback
or home-directory restore was performed.

## Validation

- `python3 -m unittest discover -s tests`: 54 tests passed. These cover site
  parsing/rendering, touch-menu actions, UMS target refusals, real GLib desktop
  discovery/launch arguments and sampled-frame encoding.
- `openspec validate --all`: 17 items passed, no failures.
- `python3 scripts/build_site.py`: passed; 58 pages, 1,134,293 bytes, 9.90 seconds.
  This includes committed-evidence checks and the binary inventory.
- The daily image and the separate optional splash-owner toplevel build passed.
- [Fresh-image app and firewall checks](shell-features/declarative-final/README.md)
  passed. Both IPv4 and IPv6 filtering and reverse-path chains are installed.
- [Current U-Boot host/UMS check](uboot-ums-host-coexist-daily.txt) passed;
  this is controller binding and storage transport evidence, not internet access.

The launcher change is archived under
`openspec/changes/archive/2026-09-22-the-shell-launches-apps-without-a-keyboard`.
Its main spec is synchronized. The broader shell change has 23/28 tasks complete;
USB and splash changes remain active. Their unchecked hardware requirements are
not waived by this checkpoint.

## Remaining work

- Record battery-only automatic startup and the complete real-finger keyboard,
  touch accuracy, window/recovery and system-control sequence. The existing user
  report establishes launcher finger usability, not every control in that list.
- Repair the physical splash-to-Linux geometry/color defect, then measure the
  complete handoff. The source audit and read-only register comparison narrow
  the next diagnostic; the daily image keeps the splash disabled.
- Characterize the BootROM/button recovery paths with physical access.
- The offline-app/help and computational Game of Life changes are proposals,
  with implementation tasks untouched. GoL depends on the static handoff repair.
  Wi-Fi remains proposed and unverified; no credentials are part of the repo.
