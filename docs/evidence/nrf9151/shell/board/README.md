# Modem shell UI on the board (task 6.3, partial)

**Evidence class: board-read.** These are native `grim` captures with injected
touch, made with `docs/evidence/design-review-leftovers/ui.py.txt` on
2026-10-27 (UTC). The operator did not touch the glass.

The builds were test-activated with `switch-to-configuration test`; the boot
default stayed `qh3i7b3f`.

- **`a8y7k25d`:** the Settings rows and the Location captures.
- **`phhkccpp`:** `cellular-off.png`. This build also stops the SIM row reading
  "Reading…" when only Location has powered the modem.

| Capture | Shows |
| --- | --- |
| `settings-rows.png` | Cellular › Off and Location › Off at the head of the right column. Before this, the service forgot on restart that the modem had answered, so the rows were hidden. It now records `seen` in `/var/lib/k230-modem/settings.json`. |
| `location-off.png` | The Location page: the switch is off and the status reads Off. |
| `location-on-searching.png` | After an injected tap on the switch. The status reads "Searching…", and the service state reads `power: on`, `location: true`, `gnss: searching`. `settings.json` holds `location: true`. |
| `shade-location-searching.png` | The shade with a hollow location glyph beside "15% · Charging". There is no cellular glyph, because Cellular is off. |
| `cellular-off.png` | The Cellular page with no SIM and Cellular off: every row shows a dash and the signal reads "No signal". |

## Before these captures

On this board, the shell user could not read the message store at
`/var/lib/k230/modem/`, because `/var/lib/k230` is `0700 root`. The state
directory moved to `/var/lib/k230-modem` (`0750 root:k230-modem`). After
deployment the old directory was gone and `sudo -u shell ls` listed
`settings.json`.

## Still open in 6.3

- **SMS:** a preview and a history entry, which need a SIM.
- **Operator:** the operator turning Location on in Settings, with the choice
  surviving a reboot.
