# Shade battery and Settings Key backlight: host renders

Keyboard-base task 6.3. Evidence class: **host render** only (Cairo through the
production `RendererCache::draw`, no compositor, no board, no glass).

Regenerate:

```
cd nix/rust-shell-client
cargo run --example render_keyboard_base_evidence -- ../../docs/evidence/keyboard-base/shell/host-renders
```

The example builds two temporary trees and reads them with
`keyboard_base::read_view_state`, the reader the live client uses:

- `with`: `power_supply/bq27220-0` (type `Battery`, capacity 64, status
  `Charging`) and `leds/k230::kbd_backlight`, no preference file (default High).
- `without`: an empty `power_supply` class and no LED.

| Files | Shows |
| --- | --- |
| `shade-with-base-*` | "64% - Charging" on the shade's hint line |
| `shade-without-base-*` | no battery element |
| `settings-with-base-*` | a Key backlight row ("High", "Lights the keys while typing"; a tap steps High, Medium, Low, Off) before Power |
| `settings-without-base-*` | no Key backlight row; Power section one row higher |

Each exists at `568x1232` (portrait) and `1232x568` (landscape). At 1232x568 Settings lays its
controls out in three columns (Wi-Fi, Brightness, Volume; Keyboard, Motion,
Key backlight when the LED exists; Power), so every control, including the
Key backlight row and the Power rows, is on the panel; the pair differs by that
one row. The Settings
data is a fixture (`evidence_render::fixture_settings`), the Volume row reads
"No audio device found" because no PipeWire graph is attached, and the grey
band under the portrait panel is the empty area below the sheet (the landscape sheet fills the panel).

Limits: this proves the paint and the hide-when-absent gating. It does not show
a real gauge, the real LED, the preference file under `/var/lib`, or the
panel. Those remain for task 6.5 (native captures on the board).
