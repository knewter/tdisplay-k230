# Shade battery and Settings Key backlight: board captures

Keyboard-base tasks 6.3 and 6.5 (partial). Board: the first board, landscape
profile (`DSI-1` transform 270), system
`c0nlmc24m0gf3y3ybim30ff77lcfsad9-nixos-system-nixos-26.11.20260919.20b1ddd`,
built from commit "Show the battery in the shade and add a Key backlight
setting" rebased on `87e1634e`. Captured 2026-10-14 00:37–00:38 UTC.

| File | Class | Shows |
| --- | --- | --- |
| `shade-landscape-grim.png` | board, native `grim` | `k230-shell-rust --surface shade`: "100% - Full" on the hint line, read from the real `bq27220-0` gauge (`capacity` 100, `status` Full at the same time) |
| `settings-landscape-grim.png` | board, native `grim` | `k230-shell-rust --surface settings`: Wi-Fi, Brightness, Volume, and the top of Keyboard. The Key backlight row is below the 568 px panel edge |
| `settings-landscape-drag-injected.png` | board, **injected** | after an injected upward drag (`tools/inject-tap.sh` on an `evemu-device` clone of the Goodix controller, panel `(480,616)` to `(120,616)`): Settings does not scroll; the file is byte-identical to `settings-landscape-grim.png` |

Capture command, as root on the board:

```
U='runuser -u shell -- env XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1'
$U k230-shell-rust --surface shade;    sleep 2; $U grim /tmp/shade.png
$U k230-shell-rust --surface settings; sleep 2; $U grim /tmp/settings.png
```

Also read on the board: `shell-keyboard-base` and `k230-battery-policy` are
active; `/var/lib/k230-keyboard-base` is `drwx------ shell shell` and
`/var/lib/k230` stays `drwx------ root root`.

Limits:

- In landscape, Settings cannot reach Motion, Key backlight or the Power rows,
  and does not scroll. That predates this change (Motion and Power were
  already below the edge) and belongs to the landscape change's task 8.3
  (`openspec/changes/the-hdmi-shell-works-in-landscape`). The Key backlight
  row is therefore not yet shown or tapped on the board; its paint is proven
  only by the portrait host render.
- No glass touch, no camera (the bench camera is disconnected), and no
  operator check of the Key backlight preference turning the LED off.
