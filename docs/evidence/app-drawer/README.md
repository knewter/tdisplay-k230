# App drawer redesign — before/after host renders

Evidence for `docs/design/app-drawer-review.md` and the
`the-app-drawer-is-redesigned` OpenSpec change. All three PNGs are real
Cairo/Pixman renders of the production `scene()`/`paint_drawer` paint
function via `k230-shell-rust --render-fixture drawer OUTPUT.png` — the same
code `RendererCache::draw` calls every live frame — at the real panel
geometry (568×1232). This is a **host build render**, not a QEMU or board
run: no compositor, no synthetic touch input, no camera. Board and
real-glass verification remain open (see the OpenSpec change's `tasks.md`).

## Commands (exact, as run)

```
cargo build --bin k230-shell-rust    # nix/rust-shell-client, debug profile
```

### `original-before-redesign.png`

The true pre-redesign drawer (3 columns, boxed tile plates, the "YOUR
DEVICE / All apps / Everything installed…" header, the "Swipe down to
return to cards" footer), captured by temporarily restoring
`navigation.rs`/`render.rs`/`service_ui.rs`/`icon.rs`/`main.rs` to their
state at `d054d16b` (the merge-base this change branched from, before any
of this change's commits) in this same worktree, rebuilding, capturing,
then restoring the current source (`git checkout HEAD -- ...`) and
rebuilding again. `cargo test --lib`/`--bin` both still passed immediately
after restoring, confirming nothing was left behind.

```
env XDG_DATA_HOME=<fixture>/applications-parent XDG_DATA_DIRS=/nonexistent \
    target/debug/k230-shell-rust --render-fixture drawer \
    docs/evidence/app-drawer/original-before-redesign.png
```

### `redesign-fixture.png`

The redesigned drawer against the same 24-entry throwaway fixture catalog
`docs/evidence/app-drawer/README.md`'s earlier revision used (`Files`,
`Terminal`, `Camera`, `Gallery`, … each `Icon=applications-other`, not
resolvable in this sandbox — every tile exercises the round,
theme-tinted-circle-with-initial fallback). Same command shape as above,
different output filename.

### `redesign-real-icons.png`

The redesigned drawer against this repo's own real installed-app catalog
and its real bundled icon theme. **First revision of this screenshot
(now replaced) got this wrong** — see §"A harness gap, not a resolution
failure" below for the full investigation the coordinator asked for.

`XDG_DATA_DIRS` is the **exact, real string the board's own session
uses**, extracted directly from the built `k230-touch-launcher` binary
(`nix/shell.nix`'s `launcherEnvironment`, shared by the touch launcher and
the coherent-shell session — "the systemd session does not run a login
shell" is that script's own comment for why it exists at all), not a
hand-assembled approximation:

```
strings /nix/store/<hash>-k230-touch-launcher/bin/k230-touch-launcher | grep XDG_DATA_DIRS
# ->
# /nix/store/sk2iq19y…-k230-handheld-desktop-entries/share:
# /nix/store/in3nc21z…-handheld-theme-icons-25.10.3/share:
# /nix/store/kv21hqgv…-foot-riscv64-unknown-linux-gnu-1.28.0/share:
# /nix/store/nyy80gvh…-htop-riscv64-unknown-linux-gnu-3.5.3/share:
# /nix/store/vf5ffka7…-mpv-riscv64-unknown-linux-gnu-0.41.0/share:
# ${XDG_DATA_DIRS:-...}
```

```
env K230_ICON_THEME=Yaru-purple XDG_DATA_HOME=<empty, unused> \
    XDG_DATA_DIRS=<the exact string above> \
    target/debug/k230-shell-rust --render-fixture drawer \
    docs/evidence/app-drawer/redesign-real-icons.png
```

`K230_ICON_THEME=Yaru-purple` matches this repo's own default bundled
theme (`nix/handheld-theme-default/default-appearance.json`'s
`"icon_theme": "Yaru-purple"`) — `--render-fixture` passes no
`AppearanceSnapshot`, so without this the resolver falls back to plain
`hicolor`, which is *not* what a themed board actually runs with.

**Result: every application in this catalog now resolves a real icon.**
No round-circle fallbacks appear in this screenshot at all. `mpv.desktop`
additionally appears as its own entry ("mpv Media...") — a real,
faithful consequence of `${videoProbe.player}/share` being one of the
real session's own `XDG_DATA_DIRS` roots (it contributes its icon *and*
its own desktop file), not a screenshot artifact.

#### A harness gap, not a resolution failure

The coordinator asked which. Checked directly, `Icon=` value by `Icon=`
value, against `/nix/store/…-nixos-system-…/sw/share/applications` and
the real `k230-handheld-desktop-entries` package:

| App | `Icon=` | Where it actually lives | Resolves once `XDG_DATA_DIRS` includes that root? |
| --- | --- | --- | --- |
| 2048, NetHack, Net (sgt-puzzles) | `applications-games` | `handheld-theme-icons` (bundled Yaru), `.../Yaru/*/categories/applications-games.png` | Yes |
| Clock, Timer | `clock-alt-symbolic` | same, `.../Yaru/scalable/status/clock-alt-symbolic.svg` | Yes |
| Editor | `accessories-text-editor` | same, `.../Yaru/*/apps/accessories-text-editor.png` | Yes |
| Weather | `weather-clear-symbolic` | same, `.../Yaru/scalable/status/weather-clear-symbolic.svg` | Yes |
| Files (nnn override) | `folder` | same, `.../Yaru/*/places/folder.png` | Yes |
| Monitor (htop override) | `htop` | **htop's own package**, `.../htop-*/share/icons/Yaru/*/apps/htop.png` (Yaru ships it directly) | Yes, once `pkgs.htop`'s own `/share` is a root |
| Terminal (foot override) | `foot` | **foot's own package**, `.../foot-*/share/icons/hicolor/{48x48,scalable}/apps/foot.{png,svg}` | Yes, once `pkgs.foot`'s own `/share` is a root |
| Video | `mpv` | **mpv's own package**, `.../mpv-*/share/icons/hicolor/*/apps/mpv.{png,svg}` | Yes, once `videoProbe.player`'s own `/share` is a root |

Every name resolves *somewhere* real, via the icon theme's own `Inherits`
chain (`Yaru-purple → Yaru → Humanity → hicolor`, already correctly
implemented in `icon.rs::theme_lookup`, unchanged by this fix) — three of
the nine (`htop`, `foot`, `mpv`) resolve only because each of those
*specific packages* ships its own icon under its own `share/` tree, which
is exactly why the real session's own `XDG_DATA_DIRS` lists them as
individual roots rather than relying solely on the bundled theme
package. The first revision of this screenshot used a hand-assembled
`XDG_DATA_DIRS` (the aggregated `environment.systemPackages` profile plus
four unrelated packages picked to demonstrate *a* real icon) that never
included `pkgs.foot`, `pkgs.htop` or `videoProbe.player`'s own `/share`
roots at all, and never set `K230_ICON_THEME` — a harness gap on this
change's own part, not anything wrong with `icon.rs`'s resolution logic
or with the desktop entries' own `Icon=` values.

**Fixed anyway, as defense in depth:** `render.rs::paint_drawer_tile` now
retries a generic `utilities-terminal` icon (confirmed present in the
bundled Yaru theme) before falling back to the letter circle, for any
application that is a terminal emulator or runs inside one
(`catalog::terminal_like`, reading `Terminal=`/`Categories=` directly
from the raw desktop file, since `gio`'s bindings expose neither as a
plain getter). This is not currently exercised by this catalog once the
harness is correct (the table above shows every current app resolving a
real, specific icon), but is a reasonable safety net matching the
coordinator's own suggested mechanism, for whatever future application
ships with an icon name genuinely absent from the bundled theme.

## What the screenshots show

- **Before:** 3 columns, boxed tile plates, ~181px prose header, a footer
  caption, ~15 tiles visible in the viewport.
- **After (fixture):** 4 columns, no plates — just a circular icon and a
  single-line ellipsized label — a slim handle and a pill search field
  instead of the header, no footer, ~24 tiles visible in the same
  viewport, rounded top sheet corners. The fallback circle is a
  strong-alpha (0.55) accent-tinted "tonal container", not a faint tint —
  coordinator finding on an earlier revision ("dark and flat") — with the
  initial in `style.text` (bright, guaranteed-contrasting), not the
  accent again.
- **After (real icons):** the same redesign against the board's own real
  catalog and its own real `XDG_DATA_DIRS`, showing every application
  resolving a real icon, zero fallback circles.

## Limits

- No theme/appearance snapshot was supplied (`theme: None`) for any of the
  three, so all three renders use the plain fallback background color, not
  a real theme's brush.
- No touch input, compositor, QEMU or board was used. This proves the
  paint code renders the intended layout on this host; it does not prove
  touch behavior, frame timing on hardware, or anything about the real
  panel.
