# Touch launcher laptop validation

Date: 2026-09-22

The Apps status-bar page is covered by the local protocol and action test. It
asserts its four named 128-pixel targets, shared foreground and distinct
background colours, 512-pixel total width, Back navigation, Terminal's
focus-or-start behaviour, and New term's deliberate second Foot launch.

```sh
python3 tests/test_touch_menu.py
nix eval --raw .#nixosConfigurations.k230.config.system.build.toplevel.drvPath
```

Both commands passed against the source tree for this change. This validates
JSON emitted to swaybar and stubbed process actions only. It is not evidence
of a real glass tap, target readability, or application launch on the panel;
those remain hardware checks in the change tasks.
