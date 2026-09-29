## ADDED Requirements

### Requirement: Cross-page dragging pages fluidly with a visible edge affordance

<!-- Grounding: implemented and host-tested (`home_screen`/`home_pager`
unit tests, including the dwell-timing, page-creation, and fling tests
named below). The rendered edge glow/arrow and "no room" highlight are
evidenced by a host Cairo render harness
(`docs/evidence/home-widget-design/`), not a board or QEMU capture; real
touch feel and daylight visibility of the affordance are UNVERIFIED on
hardware. -->

While a person holds a dragged Home item (an icon, a folder, or a widget)
within about 40px of the panel's left or right edge, Home SHALL show a
visible themed highlight and a growing arrow at that edge, and SHALL turn
to the neighboring page after about 350-400ms of continuous holding there.
Continuing to hold at the edge past that first turn SHALL keep turning
pages with a shorter repeat delay of about 260ms. Holding at the true last
page's right edge past that same dwell SHALL create a brand-new, empty page
and slide onto it rather than remaining inert. Every page turn this
triggers, and any triggered by a quick horizontal fling below, SHALL
animate as a smooth slide, never an instant jump, and the dragged item's
own on-panel position SHALL continue following the raw finger position
throughout, unaffected by the page transform. Page-count dots SHALL render
enlarged while any drag is live. A quick, deliberate horizontal drag motion
during a hold (independent of edge proximity) SHALL also turn one page
immediately. A multi-cell widget's drag hovering over a target it cannot
fit SHALL show a visibly distinct "no room here" highlight instead of the
ordinary accepting one.

#### Scenario: The edge affordance appears before the page turns

- **WHEN** a person holds a dragged item within the edge zone for less than
  the first-dwell threshold
- **THEN** a themed edge highlight and arrow are visible, growing toward
  full, and the page has not yet turned

#### Scenario: A held edge drag turns the page, smoothly, under the finger

- **WHEN** a person holds a dragged item at the panel's right edge past the
  first-dwell threshold
- **THEN** Home slides to the next page with an eased animation, and the
  dragged item stays visually under the finger throughout

#### Scenario: Continuing to hold keeps paging, faster than the first turn

- **WHEN** a person keeps holding a dragged item at the edge after the
  first page turn
- **THEN** each subsequent page turn fires after the shorter repeat delay,
  not the longer first-dwell delay

#### Scenario: Holding at the true last page's edge creates a new page

- **WHEN** a person holds a dragged item at the right edge of Home's
  current last page past the dwell threshold
- **THEN** a new, empty page appears and Home slides onto it

#### Scenario: A quick fling pages over without waiting for the edge

- **WHEN** a person makes a quick, deliberate horizontal drag motion during
  a hold, anywhere on the panel
- **THEN** Home turns one page immediately, without needing to reach an
  edge or wait out a dwell

#### Scenario: A widget dragged somewhere it cannot fit shows "no room"

- **WHEN** a person drags a multi-cell widget so it hovers over a cell (or
  cells) already fully occupied by another item of equal or larger span
- **THEN** the drop-target highlight shows the distinct "no room here"
  styling instead of the ordinary accepting highlight

### Requirement: Home's widgets are visually redesigned with distinct styles and richer content

<!-- Grounding: implemented and host-tested (clock style formatting,
`j1` forecast selection/parsing, battery ring percent/charging state, the
procedural dot-matrix digit table). Rendered appearance is evidenced by a
host Cairo render harness (`docs/evidence/home-widget-design/`) composited
over real Omarchy theme wallpaper images, not a board or QEMU capture;
daylight readability and on-device color/font reproduction are UNVERIFIED
on hardware. -->

The Clock widget SHALL offer at least four selectable visual styles,
researched from current mobile-platform and community widget design
(`docs/design/clock-widget-research.md`): a heavy centered stacked hour/
minute pair, a thin centered single time line, a procedurally drawn
dot-matrix readout, and a drawn analog face (ticks and hands only, no dial
fill or ring) with an accent-colored minute hand -- each choosable from the
widget picker, which SHALL render a live preview of each widget kind's
actual content inline in its own row. The Battery widget SHALL show its
charge as a themed ring with a distinct charging indicator when charging,
and its absent state SHALL pair the existing "No battery info" wording with
a muted outline battery glyph. The Weather widget SHALL show the current
temperature as a large numeral, a drawn condition icon distinct per
condition family (at minimum sun/cloud/rain/snow/fog/storm), the location
name when available, today's high and low, and a short multi-entry forecast
strip when forecast data is available. No widget of any kind SHALL paint a
card background, surface fill, or border behind its content -- every widget
sits directly on the wallpaper; legibility SHALL instead come from a halo
or glow computed from the theme's own resolved color for that glyph (a
light halo behind a dark glyph, a dark halo behind a light glyph), never a
fixed shadow color that ignores which theme is active.

#### Scenario: A person can choose a clock style from the picker

- **WHEN** a person opens the widget picker's Widgets page
- **THEN** more than one Clock entry is listed, each showing a live preview
  of that style's actual rendered content, and long-pressing one places a
  clock in that style

#### Scenario: A charging battery shows a distinct indicator

- **WHEN** the Battery widget's underlying state reports a battery that is
  charging
- **THEN** the widget's ring shows a charging glyph distinct from its
  non-charging appearance

#### Scenario: The weather widget shows a forecast strip when data allows

- **WHEN** a fresh weather reading includes forecast entries
- **THEN** the widget shows a short strip of upcoming entries, each with its
  own time label, temperature, and condition glyph

#### Scenario: No widget paints anything behind its own content

- **WHEN** any widget (of any kind) is shown on a Home page over any
  wallpaper
- **THEN** nothing is visible behind that widget's glyphs but the wallpaper
  itself -- no card fill, no border, no corner radius

#### Scenario: A glyph's halo follows its own color, not a fixed shadow

- **WHEN** a widget paints a light-colored glyph, and separately when it
  paints a dark-colored glyph
- **THEN** the light glyph is haloed in a dark color and the dark glyph is
  haloed in a light color
