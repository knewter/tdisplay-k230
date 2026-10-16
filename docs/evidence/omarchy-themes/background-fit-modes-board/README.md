# Background fit modes and user overlays on the board, 2026-10-16

Evidence class: native `grim` captures on the board's HDMI output. Inputs were
injected: a uinput pointer and the compositor trackpad command for the chooser
UI, and the installed `k230-theme` CLI (`preview --fit` then `activate --fit
--expected-generation`) for the light-theme pass. No finger touched glass.
The DSI panel was not exercised.

- System: `/nix/store/m1c3jq413s8acils9y6jrpdk02xq5lmz-nixos-system-nixos-26.11.20260919.20b1ddd`,
  live-deployed from branch `integ-1016` at `f082393a`. That is master
  `65ee0201` plus side-edge Back `ec1bf497` and this change's `f082393a`.
  Rebased onto master, the same commits landed as `3a912936` and `681bd4d8`.
- HDMI mode: the HP 27wm came up at 1280x720 after the deploy and at 1280x800
  after the shell restart. File names carry the mode of each capture.

## Task 3.2: each fit mode, one dark and one light theme

The dark theme was cycled through the chooser by tapping the "Backgrounds ·
<mode>" heading at (790, 61); each tap answered "Background fit: <mode>". The
light theme went through the CLI. For each mode, Home was captured with the
chooser closed.

| Mode | Dark: retro-82, "In the groove" | Light: catppuccin-latte | Reads as |
| --- | --- | --- | --- |
| crop | `dark-retro-82-crop-1280x720.png` | `light-catppuccin-latte-crop-1280x800.png` | cover-cropped; no bars |
| fit | `dark-retro-82-fit-1280x720.png` | `light-catppuccin-latte-fit-1280x800.png` | whole image, pillarboxed left and right |
| center | `dark-retro-82-center-1280x720.png` | `light-catppuccin-latte-center-1280x800.png` | native pixels centred (the sources are larger than the output, so this is the middle region) |
| fill | `dark-retro-82-fill-1280x720.png` | `light-catppuccin-latte-fill-1280x800.png` | stretched to the full frame; no bars, no crop |
| solid | `dark-retro-82-solid-1280x720.png` | `light-catppuccin-latte-solid-1280x800.png` | a flat palette `background` colour; the image is not drawn |

`chooser-heading-tap-fit-1280x720.png` shows the chooser right after the first
heading tap.

Persistence: with `fit` chosen, `background-selections.json` gained
`"fits": {"<source key>": "fit"}`. After `systemctl restart shell-ui.service
theme-helper.service` at 2026-10-16T15:47:55Z, Home was still pillarboxed
(`dark-retro-82-fit-after-restart-1280x800.png`). Choosing `crop` again
removed the `fits` table, since crop is the default and is never stored.

## Task 3.4: a user overlay

Three entries were placed in `/home/shell/.config/omarchy/backgrounds/`:
- `overlay-test.png`, a copy of a committed host render;
- `link.png`, a symlink to `/etc/hostname`;
- `notes.txt`.

`k230-theme preview` listed `user-overlay-test.png` among the backgrounds and
reported `overlay link.png: not a regular file` and `overlay notes.txt:
unsupported suffix` under `unknown`. The chooser showed a "User overlay test"
slice (`overlay-chooser-1280x800.png`). Tapping it answered "Background
applied to Home". After a shell and helper restart at 2026-10-16T15:50:31Z,
Home still showed the overlay (`overlay-home-after-restart-1280x800.png`).

Afterwards the original background was re-selected and the three files and
the folder were removed. The over-256 MiB case was not run on the board; the
host test covers it.

## Found on the board and fixed

The heading names the fit mode, which made it longer. On the wide layout it
then ran into the fixed-position "Applied to Home" label
(`chooser-status-overlap-before-fix-1280x800.png`). Commit `05f63ff3` places
the label after the measured heading and drops it when there is no room; the
bottom status line repeats it. The fix was checked by host render at
1280x800 and 1232x568 with the longest mode name ("center"). It has not yet
been redeployed.
