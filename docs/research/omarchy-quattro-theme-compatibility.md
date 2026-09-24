# Direct Omarchy Quattro theme compatibility

Research date: 2026-09-23. This is a source survey and implementation plan,
not a working importer or physical-board result.

## Revisions inspected

- Latest published release observed through GitHub's release API:
  [v4.0.4](https://github.com/omacom/omarchy/releases/tag/v4.0.4), published
  2026-09-15, tag revision `c668141e9c42b13c80c9ca4ea108e11708c5e8a5`.
- Newer `quattro` branch inspected at
  [`28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`](https://github.com/omacom/omarchy/tree/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c).
  Its most recent merge remembers wallpapers per theme. This branch snapshot,
  rather than an assumed stable release schema, defines the initial target.
- Community sample:
  [Fuchsblau at `aa7fde043ae60603c3ecc6fd6ac3b6674cacab04`](https://github.com/fuchsblau/omarchy-fuchsblau-theme/tree/aa7fde043ae60603c3ecc6fd6ac3b6674cacab04).
  Read its palette, icon selector, and four section override files; enumerated
  its three JPG backgrounds. The images were not decoded or visually reviewed.

Discovery used `gh api repos/omacom/omarchy/releases/latest`,
`git ls-remote ... refs/tags/v4.0.4`, shallow sparse clones, `git rev-parse HEAD`,
and source reads. No upstream theme installer was executed. These checkouts
are research inputs, not installed device configuration.

## Which repository gets cloned?

Omarchy's own themes are directories inside its
[`themes/` collection](https://github.com/omacom/omarchy/tree/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/themes).
Community themes put the theme at repository root. The
[registry](https://github.com/omacom/omarchy-theme-registry) contains catalog
metadata, not the complete theme assets. Support both actual source layouts:
select a community checkout directly, or discover/select a built-in member.
An existing clone must remain usable with ordinary `git pull`; generated
configuration and persisted preferences belong outside it.

## Compatibility inventory

The following table is a proposed mapping, not a claim of existing support.
Primary source links are pinned so tests can distinguish upstream changes.

| Upstream input | Proposed handheld treatment |
| --- | --- |
| `colors.toml` | Preserve all authored keys and expose raw and resolved values; implement the complete alias/derivation behavior, not a fixed small palette. |
| `mode`, `theme_type`, `light.mode` | Same precedence, followed by background luminance detection and dark fallback. |
| `shell.toml` | Complete replacement of generated shell defaults, then normal consumer fallbacks for missing values. |
| `shell.<section>.toml` | Replace that section, with optional matching header; this is not a key merge into the generated section. |
| Machine shell override | Overlay individual keys after theme resolution, outside the clone. |
| `controls`, `font`, `spacing` | Shared control states, typography and spacing across our surfaces; report handheld scaling/minimum-target adaptations. |
| `launcher` | Installed-app drawer colors, selection, borders and scrim. |
| `menu`, `popups`, `tooltip` | Card chrome, Settings rows/dialogs/OSD, contextual hints, with per-surface mapping documented. |
| `notifications`, `image-picker` | Notification shade/previews and theme/background chooser. |
| `hyprland` color/border references | Resolve data references for our Sway card borders; no Hyprland process required. |
| `bar`, `lock`, `polkit` | Retain/report values whose matching surface is absent. Do not add a permanent bar or lock screen to satisfy a theme. |
| `icons.theme` | Select installed freedesktop icon theme and inheritance; report missing dependency and use a labeled fallback. |
| `backgrounds/` and user overlay | Enumerate every supported image/video candidate, previews and selection; preserve chosen wallpaper per theme. |
| `preview.png`, `preview-unlock.png`, `unlock.png` | Theme preview versus lock/unlock assets remain distinct; preserve and identify assets for absent surfaces. |
| App color files | Parse supported appearance fields into installed-app adapters; enumerate absent apps and unsupported settings. |
| `keyboard.rgb` | Explicitly not applicable to this hardware; the on-screen keyboard still follows shell colors. |
| Lua, scripts, hooks, terminal launch directives, extension installers | Never execute; leave files intact and report the boundary. Read legacy terminal palette fields as data only. |

### Palette and template behavior

The authoritative resolver is
[`bin/omarchy-theme-color`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/bin/omarchy-theme-color).
It handles canonical/short neutral names; named and bright chromatic colors;
`color0` through `color15`; purple aliases; orange and brown; cursor and
selection roles; and derived shades. Explicit selection foreground must not
be lost. Custom keys matter: Fuchsblau supplies `hairline`. Resolution order
matters when canonical and ANSI values coexist, so use differential fixtures
against this resolver, not an approximate reinterpretation of the prose.

[`omarchy-theme-set-templates`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/bin/omarchy-theme-set-templates)
defines direct, `_strip`, `_rgb`, mixing, and gradient substitutions, template
precedence, and section replacement. Run this trusted pinned helper against
data in isolated staging; never evaluate theme-authored code. Our validation
must report unresolved substitutions and reference cycles explicitly rather
than assuming the upstream helper rejects them.
The upstream default
[`shell.toml.tpl`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/default/themed/shell.toml.tpl)
is the initial default-role inventory. Track every key rather than only the
palette example in the manual.

[`Border.qml`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/shell/Commons/Border.qml)
and its `BorderGeometry.js` dependency define solid/gradient color, alpha
multiplication, cross-section references, CSS-style width expansion, per-side
overrides, and legacy gradient keys. Gradients require real rendering on
capable shell surfaces; using the first stop everywhere is incomplete.
[`Style.qml`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/shell/Commons/Style.qml)
also reads rounding and gaps from live Hyprland options. These are not secretly
portable `shell.toml` fields: executable compositor configuration is an explicit
boundary, and our gesture geometry remains owned by the handheld design.

### Background behavior

[`omarchy-theme-bg-next`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/bin/omarchy-theme-bg-next)
enumerates JPG/JPEG, PNG, GIF, BMP, WebP, MP4, M4V, MOV, WebM, MKV, and AVI,
combining theme and user directories with sorted cycling. A suffix does not
prove that its codec is decodable on the handheld.
[`omarchy-theme-set`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/bin/omarchy-theme-set)
remembers per-theme selection, falls back when needed, and cycles when the
same theme is selected again. Preserve that explicit cycling action while
making ordinary refresh idempotent so a file update does not change wallpaper.

[`Background.qml`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/shell/plugins/background/Background.qml)
draws still images with aspect-preserving crop and delegates desktop video to
OWE. Our implementation needs its own bounded playback adapter; importing a
palette cannot supply that behavior. Offer crop/fit/fill/center/solid choices
as handheld preferences outside the clone, using upstream crop by default.
Static backgrounds must cost no repeated decode during dragging. Video must
stop decoding when covered, and must not undermine card input budgets.

## Acceptance boundary

### Can we reuse their swap mechanism?

Yes, with a small platform adapter. Reading the complete pinned
`bin/omarchy-theme-set` shows the concrete sequence:

1. Normalize the selected name, acquire `flock`, remember the previous wallpaper.
2. Stage built-in files then the user theme under `current/next-theme`; filter
   executable inputs from recognized cloned themes; derive a legacy palette if needed.
3. Run `omarchy-theme-set-templates`, then replace the current theme directory
   and write `theme.name`.
4. Send base64 palette and shell TOML to `omarchy-shell shell applyTheme`, or
   combine them with the background paths in `background themeTransition`.
5. Release the lock, run app retint helpers in parallel, invoke the theme-set
   hook, and warm picker caches.

The receiver in
[`shell/shell.qml`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/shell/shell.qml)
decodes the two payloads and loads Color/Style. The transport in
[`bin/omarchy-shell`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/bin/omarchy-shell)
uses Quickshell IPC. That small boundary can instead notify our shell.
Reuse the palette/template helpers and data paths; adapt activation, IPC and
installed-app reloads. `OMARCHY_THEME_HEADLESS=1` is useful for offline generation
but intentionally bypasses live shell and app notification.

[`omarchy-theme-set-foot`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/bin/omarchy-theme-set-foot)
uses [`omarchy-theme-osc`](https://github.com/omacom/omarchy/blob/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/bin/omarchy-theme-osc)
to send foreground/background/cursor/selection and ANSI colors to running Foot
PTYs. Our adapter should scope delivery to the session's verified terminals;
the generated `foot.ini` handles subsequent launches. This is an existing
useful integration, not a need to invent terminal theming.

The upstream script is not drop-in here: it invokes Hyprland, Quickshell,
GNOME settings, desktop-app helpers and user hooks. Also, its `rm` then `mv`
replacement leaves a reader gap and failed shell IPC is tolerated. Keep a
narrow patch/adapter for generation publication and acknowledgement rather
than claiming it already provides transactional rollback. Source inspection
establishes feasibility, not a host execution or physical compatibility pass.

### Completion means usable themes

An unchanged checkout must load, stay Git-clean, retain all colors, correctly
apply the available surface overrides, expose every background choice, select
its icons, and survive refresh/reboot/rollback. Every input gets a compatibility
classification. Missing implementations for present handheld surfaces remain
open work, not permission to call a partial import complete. Absent apps,
lock/unlock services, RGB hardware, and executable desktop configuration are
listed distinctly from implementation gaps. Include attribution/license review
before redistributing wallpapers or copied upstream code; this research adds
no upstream bitmap assets.
