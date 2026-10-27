## 1. Stylesheets

- [x] 1.1 Raise the GTK3 stylesheet's menu bar, menu, button, entry, spin button, tab, check/radio, switch, scale and scrollbar sizes; add `render_gtk4_css`; generate and link `gtk-4.0/gtk.css`; install it in the pinned default generations; regenerate the defaults. Proof: `python3 -m unittest tests.test_theme_gtk tests.test_handheld_app_themes tests.test_handheld_theme_default` and `python3 tools/generate_default_gtk.py --check`.
- [x] 1.2 Parse both stylesheets with GTK 3.24 and GTK 4.22 under Xvfb and read the laid-out control sizes. Host evidence only: GTK3 menu bar 72, popup item 76, button 74; GTK4 header button 64, button 72, list row 72.

## 2. Board (hardware-only)

- [x] 2.1 Test-activate a build, launch Net and Files, and capture them with grim (injected touch). Menu bar and header buttons must measure at least 64 px and no window may overflow the panel. Record under `docs/evidence/gtk-touch-floor/`.
  Done 2026-10-27 (build `dhmp8mdi…` and `kllh24ww…`, injected taps): Net's menu bar is 72 px and its toolbar 72 px; Files' path-bar button is 88 px and sidebar row 84 px; both windows fit 1232x568. `docs/evidence/gtk-touch-floor/`.
- [ ] 2.2 The operator taps Net's menus and Files' header on glass. Physical proof: a timestamped operator report tied to the installed build.
