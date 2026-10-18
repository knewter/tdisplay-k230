## Context

Layer: userspace only. The work is in `nix/rust-shell-client/src/render.rs`
(Cairo and Pango on Pixman, CPU rendering on the K230's 1.6 GHz core) and,
for the card shell, `nix/card-shell/`. No kernel, device tree or image-level
change.

The panel is a 4.1" AMOLED, 1232x568 landscape (568x1232 portrait), about
2.07 px/dp. Touch targets are at least 99 px. Secondary text is at least
about 26 px (12.5 dp) at 100%. The Vision page offers four text steps and a
high-contrast mode. Home widgets cancel the step in `paint_widget_card`,
except for the Clock date, which follows it.

Fonts already on the image: DejaVu Sans (`FONT_FAMILY`) and Inter
(`CLOCK_FONT_FAMILY`, the static collection with Thin to Black weights).

## Direction

The shell is a dark glass handheld seen mostly over a wallpaper. It should
look like one instrument: quiet surfaces, large clear numerals, and a single
bright colour used only for what is live or chosen. Three ideas carry it.

1. **The accent marks what is live.** On the Clock it is the minute. On the
   Battery ring it is the charge. In Settings and the Vision page it is the
   current choice and the single primary action. Links and secondary
   actions use the foreground colour, not the accent.
2. **Two faces, two jobs.** Inter is the display face for numerals and
   headings (its weights range from Thin to Black). DejaVu Sans stays for
   body text and labels, where its wide letters help at small sizes and the
   card shell already shares it.
3. **Structure carries meaning.** A card edge, a divider or an accent rule
   appears only when it says something: a group, a selection, a drag target.

## Decisions

### Landed in this change: the Clock

1. **Hour in the foreground, minute in the accent, in every style.** The
   minute is the part a person reads and the part that changes each minute.
   One rule across Bubble, Thin and dot-matrix lets the styles differ in
   silhouette and weight, not in colour logic. Analog already had an accent
   minute hand and keeps it. The Braun precedent in
   `docs/design/clock-widget-research.md` (#9) is one accent, used once.
2. **Bubble: tighter and larger.** The two lines sit 0.92 em apart instead of
   1.13, so the pair reads as one block, and the size rises from 30% to 38%
   of the card's height, capped at 46% of its width. `bubble_lines` is the
   one source of this geometry for the painter and the clearance test.
3. **Thin: Light, with a quiet colon.** One line, drawn in three runs
   (`hero_glow_run`): the hour, a colon at 60% opacity, the minute. Inter
   Light, not Thin, because the Thin weight's hairlines vanish over a
   photograph even with the halo.
4. **Dot matrix: a lamp grid.** Unlit dots are drawn at 16% opacity with half
   the radius of lit ones, so the block reads as a display and not as loose
   dots. The minute takes the accent; the colon takes the foreground.
5. **The date is quiet and bigger.** "Fri, Oct 16" in Inter Semibold, mixed
   case, no tracking, foreground colour, centred, with the same halo as the
   time. Tracked capitals cost about a quarter of their width and are a
   label style: they read as a caption. The date is information, so it
   reads as text. The floor rises from 26 to 32 px at 100% because
   mixed-case text of one size looks smaller than capitals. The metrics
   still grow with the Vision step, fit the card's width, and make the time
   yield, as in `the-clock-widget-date-is-readable`. The tracking flag is
   gone, since there is no tracking left to drop.
6. **Same halo.** Legibility over any wallpaper still comes from the
   existing `draw_layout_halo` (8 samples), now also around the accent
   minute. Nothing new is drawn per frame, and the clock still redraws once a
   minute.

### Proposed for the rest of the shell

7. **Type scale, five roles.** Sizes are design pixels at 100%, before the
   Vision step.

   | Role | Size | Face and weight | Used for |
   | --- | --- | --- | --- |
   | Display | 60 to 180, from the cell | Inter Heavy or Light | Clock, temperature, battery percent |
   | Title | 40 | Inter Bold | Settings, Notifications, Vision |
   | Body | 30 | DejaVu Sans | Row values, search text |
   | Label | 26 | DejaVu Sans, Bold when it names a group | Row names, section labels |
   | Caption | 26 floor | DejaVu Sans | Hints and secondary lines |

   There is no size below 26. Section labels use sentence case; tracked
   capitals go away, and the Battery details grid labels ("CURRENT") switch
   to Label.
8. **Spacing rhythm.** Multiples of 8 px: 8 inside a row, 16 between rows,
   24 around a card's content, 32 between groups. Cards keep a 99 px minimum
   touch height. The existing `visual_inset` and layout step scaling stay the
   only way to apply the Vision step.
9. **Three card treatments, by job.**
   - *Group*: the current flat tint, for containers of rows.
   - *Control*: a row that acts. A slightly stronger tint and a 1 px
     top-edge highlight made from the theme's text colour at 10%, which is a
     single cheap line and no blur.
   - *Chosen*: the current choice. The accent at 18% fill and a 2 px accent
     rim. Today the chosen Vision segment is grey with orange text.
   Radii follow the job: 24 for groups, 16 for controls, a full pill for
   chosen segments and chips.
10. **One accent rule.** Per surface, the accent marks at most the current
    choice and one primary action. Links, "Done" and "Close" use the
    foreground colour with a chevron. The theme still supplies both colours;
    on a theme whose accent has low contrast against the card, the renderer
    already falls back to the foreground colour.
11. **One icon style.** A 3 px round-capped stroke, monochrome in the
    foreground colour, drawn as vectors (like the Shade's brightness and
    volume glyphs today), 48 px square for rows and 64 px in the drawer.
    Settings rows get a leading glyph. Theme icons for apps are unchanged.
12. **Home widgets and the dock.** Widgets keep "no card, halo for
    contrast" and adopt the Display role. The dock takes the Control
    treatment instead of its own heavier slab, so it shares edges with the
    Shade and Settings.

## Rejected

- **A new display font for the whole shell.** The only candidates are
  packages not on the image, and each adds closure size and a licensing
  line. Inter and DejaVu already cover the need.
- **Frosted glass cards.** They need a blur of the wallpaper, which costs
  many full-screen passes on the CPU and makes the Shade slower to open.
- **An accent-coloured date.** It was the previous design. Two
  accent elements compete, and a small bold caption in the accent colour is
  harder to read on a wallpaper close to the accent (the orange backdrop in
  the renders).
- **A larger date only at big steps.** The operator's complaint was at 100%
  too. The floor applies at every step.
- **Colouring the hour instead of the minute.** The hour changes once an
  hour; the accent would sit unused most of the time.
- **Inter Thin for the Thin style.** The hairline strokes are lost over
  photographs, even with a halo.

## Risks

- The Clock's 100% pixels change on purpose. `tests/responsive_pixel_identity.rs`
  passed with its baselines unchanged, so the first slice
  needs no baseline update. Later slices will change Settings and Vision
  pixels, and each must update the baseline deliberately and say so.
- Mixed-case Inter at 32 px is, in the host renders, similar in weight to
  the old tracked capitals at 26 px. Whether it is readable on the glass is
  not known until the operator looks.
- The accent minute depends on each theme's accent. A theme whose accent is
  close to the foreground loses the two-tone effect but stays readable.
- The `the-clock-widget-date-is-readable` change states a 26 px floor. The
  new 32 px floor satisfies it, so both can land in either order.
