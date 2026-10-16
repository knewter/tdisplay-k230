## Why

The shell looks assembled, not designed. The operator said the Home Clock
"could use a redesign" and that its text was too small. The panel captures
under `docs/evidence/coherent-shell/accessibility-scale/board/` and
`docs/evidence/home-widgets/clock-date/` show the same few problems on every
surface:

- **The accent is spent everywhere.** On Settings (`board/22`) every link,
  value and heading action is the same orange: Done, Vision, Themes, the
  Wi-Fi arrow. Nothing says which one matters. On the Clock the tracked date
  took the accent, while the time, the part that changes, had none.
- **Selection is nearly invisible.** On the Vision page (`board/23`) the
  chosen text size is a grey tile with orange text; the other three look
  almost the same.
- **There is no type scale.** Sizes of 12, 13, 14, 15, 17, 18, 19, 25 and 26
  px are hard-coded across `render.rs`. Section labels are muted body text,
  the Battery widget uses tracked capitals, the Clock used tracked capitals
  and Settings uses sentence case. A person cannot learn what size or case
  means "label".
- **Cards are one flat treatment.** The drawer search, Settings rows, Shade
  controls and Vision segments all use the same low-contrast tint on the same
  16 px radius, whatever their job. The dock is a heavier slab, so Home and
  the rest look like different products.
- **Icons come from three places.** App icons are the theme's, Settings rows
  have none, and the Shade draws its own small vector glyphs.

The Clock is the first and most visible instance, and this change restyles it.
The rest becomes a stated visual language so later work lands consistently.

## What Changes

- **Clock (implemented here).** Every Clock style follows one rule: the hour
  is the foreground colour and the minute, the part that changes, takes the
  theme accent. The Bubble style stacks the two numerals closer and larger
  as one mass. The Thin style is a real Light weight with a quiet colon. The
  dot-matrix style keeps its unlit dots faintly visible and puts the minute
  in the accent. The date becomes one neutral sentence-case line ("Fri, Oct
  16") in Inter Semibold, no longer tracked capitals in the accent, at 32 px
  or more at 100% (up from 26).
- **A shell visual language (proposed).** A type scale of five roles, one
  spacing rhythm, three card treatments by job, one rule for the accent, and
  one icon style, applied surface by surface to Home widgets, the dock, the
  drawer, the Shade, Settings and the Vision page. See `design.md`.

## Non-goals

- No new font packages. Inter and DejaVu Sans are already on the image.
- No colour is hard-coded. Everything comes from the active theme through
  `VisualStyle`/`AppearanceSnapshot`.
- No blur, shadows with a large radius, or per-frame animation. The shell
  renders on the CPU.
- The Vision step guarantees do not change: every surface still reflows at
  100/130/160/200% and high contrast, in both orientations.
- The Battery and Weather widget faces, the dock, the drawer, the Shade,
  Settings and the Vision page are not restyled in this change's first
  slice. They are open tasks.

## Board

Host renders prove the layout and the theme behaviour. The restyle's real
test is the operator's look at the glass over the wallpaper, so group 5 stays
open until native `grim` captures and the operator's judgement exist. QEMU
does not apply.
