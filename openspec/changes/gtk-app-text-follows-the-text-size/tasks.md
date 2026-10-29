## 1. Host: which setting GTK4 honours

- [x] 1.1 Under a headless Wayland Sway (planned as Xvfb; Wayland is what the
  board runs) with GTK 4.22 and libadwaita, launch a probe window
  three ways and read the laid-out height of a label and a `.caption` label:
  - with the GSettings keyfile backend setting `font-name` and
    `text-scaling-factor`;
  - with `gtk-font-name` in `gtk-4.0/settings.ini`;
  - with neither.

  Record which one GTK4 honours in `docs/evidence/gtk-text-size/host/`.
  Proof: the probe script and its output. This is host evidence only.
  *Done 2026-10-29, host (`docs/evidence/gtk-text-size/README.md`): GTK
  4.22.4 and libadwaita 1.9.3 ignore the keyfile's `font-name` and
  `text-scaling-factor` and honour `gtk-font-name` in `settings.ini`, with
  captions at about 0.82× the base font.*

## 2. Adapter

- [x] 2.1 The GTK3 and GTK4 renderers in `tools/theme_gtk.py` take the text
  step: GTK3 `gtk-font-name` is 13 pt × the step, rounded, and GTK4 gets the
  mechanism task 1.1 found. `tools/app_appearance.py prepare` reads the step
  from the generation's `appearance.json` (where `theme_activate` records the
  saved `theme_vision` choice, so GTK and the shell read one value).
  Regenerate the pinned default generation. Proof:
  `python3 -m unittest tests.test_theme_gtk tests.test_handheld_app_themes tests.test_handheld_theme_default`
  and `python3 tools/generate_default_gtk.py --check`, with new tests for
  each step and for a changed step producing a new generation id.
  *Done 2026-10-29, host: the three suites ran 43 tests, OK, and the
  `--check` passed. New tests cover every step's point size, GTK4's font
  line, a step of 200% producing a new generation with 26 pt in both files,
  and an unknown step being rejected.*

## 3. Board (hardware-only)

- [x] 3.1 Test-activate the build. Open Files and Net at 100%, then set the
  text size to 200% in Settings, reopen both and capture each with grim
  (injected touch). The text must be larger at 200% than at 100%, and both
  windows must fit 1232x568. Proof: `docs/evidence/gtk-text-size/board/`.
  *Done 2026-10-29, board, injected touch with native grim captures, builds
  `njzllqxw…`, `yrfr1x6b…` and `2867v7pm…` (`docs/evidence/gtk-text-size/README.md`).
  Files' labels went from 10 to 14 px ink at 100%, and both apps doubled at
  200% and fit 1232x568. Net's menu scrolls at 200%. The run found two
  defects, both fixed here: GTK3 ignores `settings.ini` for its font (now
  set in `gtk.css`), and step changes did not relink `~/.config` (now
  linked through `active`). Files' slow folder load predates this change.*

- [ ] 3.2 The operator reads Files at 100% on glass. Physical proof: a
  timestamped operator report tied to the installed build.

## 4. Land

- [ ] 4.1 Merge to `master`, push, check CI, and archive with its spec
  synced once tasks 1-3 are done. Proof:
  `openspec validate gtk-app-text-follows-the-text-size --strict`.
