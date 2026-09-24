# Native appearance payload checkpoint

Observed 2026-09-23 at source commits `6829f574b9e3c917f7f6464eca50829fdf70ad6e`
and `ef7b2a8c57f935f4aa12c2a3e0d1301cde5f030a`.
The pinned helper still resolves Omarchy colors/templates. The small adapter
types its generated `shell.toml` into a bounded `appearance.json` per immutable
generation. It retains every generated section/key, including gradients with
authored stop order/angle, separate alpha, numeric spacing, and per-side border
widths. The theme command package includes this adapter; the pinned Catppuccin
default includes a derived payload bound to an ID hashing the source colors,
icon selector and canonical token payload without self-reference.

The native launcher receiver stages this payload with its palette during
`prepare`, adopts it before a redraw ACK, restores it on rollback, and loads
the selected generation on restart. It exposes brush, border, number, icon
theme, safe still-background path and generation serial getters. A missing or
invalid payload is rejected instead of displaying a partly themed generation.
The current `touch-launcher.c` still consumes only its earlier palette fields;
drawer/card rendering of the new getters is a separate integration task.

| Generated section | Fields in pinned default | Intended consumer state |
| --- | ---: | --- |
| `launcher` | 12 | Drawer; new native getters available, rendering pending |
| `menu` | 12 | Card/Settings chrome pending |
| `notifications` | 6 | Notification surface pending |
| `controls` | 22 | Controls/keyboard state rendering pending |
| `popups`, `tooltip` | 5 each | System overlays pending |
| `image-picker` | 7 | Background chooser pending |
| `font`, `spacing` | 1, 2 | Handheld scale adaptation pending |
| `bar`, `lock`, `polkit`, `hyprland` | 7, 11, 10, 2 | No corresponding shipped handheld surface/config; retained as data, not applied |

Commands and results:

```text
python3 tests/test_handheld_theme_rendering.py       PASS 3 host tests
python3 tests/test_handheld_theme_default.py         PASS 1 host test
python3 tests/test_shell_appearance_receiver.py      PASS 6 native host tests
python3 tests/test_omarchy_theme_activation.py       PASS 8 host tests
python3 tests/test_omarchy_theme_resolution.py       PASS 4 host tests
python3 tests/test_omarchy_theme_sources.py          PASS 5 host tests
python3 tests/test_omarchy_theme_transaction.py      PASS 13 host tests
cc -std=c11 -Wall -Wextra -Werror -fsyntax-only nix/touch-launcher/appearance.c $(pkg-config --cflags json-glib-1.0)
                                                  PASS native host syntax
openspec validate the-shell-loads-omarchy-themes --strict
                                                  PASS
nix build --no-link .#handheld-theme-command .#handheld-theme-default --print-out-paths
                                                  PASS package cross-build
```

Build outputs: `/nix/store/w3xbmli5ncdcyvvxdb7qmpp5hi767588-handheld-theme-command-0.1`
and `/nix/store/zahja8nizkmm3mg21k6g81pg0r4cfzfb-handheld-theme-default-28ceaae7`.
These are host/package checks. There is no changed image, display capture,
physical interaction, rollback-on-glass or full surface compatibility proof
from this checkpoint. The existing opt-in receiver remains disabled by default.
