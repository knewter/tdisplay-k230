## 1. Host: which setting GTK4 honours

- [ ] 1.1 Under Xvfb with GTK 4.22 and libadwaita, launch a probe window
  three ways and read the laid-out height of a label and a `.caption` label:
  - with the GSettings keyfile backend setting `font-name` and
    `text-scaling-factor`;
  - with `gtk-font-name` in `gtk-4.0/settings.ini`;
  - with neither.

  Record which one GTK4 honours in `docs/evidence/gtk-text-size/host/`.
  Proof: the probe script and its output. This is host evidence only.

## 2. Adapter

- [ ] 2.1 The GTK3 and GTK4 renderers in `tools/theme_gtk.py` take the text
  step: GTK3 `gtk-font-name` is 13 pt × the step, rounded, and GTK4 gets the
  mechanism task 1.1 found. `tools/app_appearance.py prepare` reads the step
  from `theme_vision.load`. Regenerate the pinned default generation. Proof:
  `python3 -m unittest tests.test_theme_gtk tests.test_handheld_app_themes tests.test_handheld_theme_default`
  and `python3 tools/generate_default_gtk.py --check`, with new tests for
  each step and for a changed step producing a new generation id.

## 3. Board (hardware-only)

- [ ] 3.1 Test-activate the build. Open Files and Net at 100%, then set the
  text size to 200% in Settings, reopen both and capture each with grim
  (injected touch). The text must be larger at 200% than at 100%, and both
  windows must fit 1232x568. Proof: `docs/evidence/gtk-text-size/board/`.
- [ ] 3.2 The operator reads Files at 100% on glass. Physical proof: a
  timestamped operator report tied to the installed build.

## 4. Land

- [ ] 4.1 Merge to `master`, push, check CI, and archive with its spec
  synced once tasks 1-3 are done. Proof:
  `openspec validate gtk-app-text-follows-the-text-size --strict`.
