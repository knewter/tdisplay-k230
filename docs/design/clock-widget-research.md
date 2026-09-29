# Clock widget research

Board feedback on `home-widget-design` (round 2), verbatim: "the widgets
don't have to have a background like they do and the clock looks like shit
browse the web find dope clock widgets plz." This is a survey of standout
clock-widget/lock-screen-clock designs across current mobile platforms,
community widget tools, and desktop "rice" culture, done before touching any
code, to ground the redesign in real precedent rather than another guess.
No trademarked asset (a specific typeface file, a platform's exact icon, a
brand's exact color) is copied; what's taken from each is the *design
principle* -- typography choice, weight contrast, layout, and color use.

## Surveyed designs

### 1. Google Pixel lock-screen clock ("two-line"/"bubble")
Android 12 introduced a large two-line stacked clock as the lock-screen
default; Android 13 added a one-line/two-line toggle; Android 14 exposed
eight preset styles plus sliders for width/height/roundness/slant, and a
later build added a "rounded vs. sharp" font toggle. The "bubble" look
several of these presets share: extremely heavy weight, generously rounded
terminals, both digits at the same visual weight (no accent-vs-plain split
within the number itself), centered, filling most of the available width.
**Principle:** a hero numeral reads as "bubble" from weight + roundness, not
from color -- a heavy, round-terminal face at a huge size is most of the
effect on its own.

### 2. Pixel "thin"/one-line style
The same Android 14 preset set includes thin, single-line variants --
`HH:MM` on one line at a much lower weight than the bubble style, still
large. **Principle:** contrast between styles should come from a real
weight-axis swing (very heavy vs. very light), not just a layout change; a
thin style needs an actually thin face, not a bold face shrunk down.

### 3. Pixel "At a Glance" home-screen widget
Google's own At a Glance widget struggled with legibility over bright/busy
wallpapers for years; a 2025 fix added an optional semi-transparent
pill-shaped backdrop toggle, and Android 16 separately introduced an
"outline text" mode for lock-screen typography replacing the older
"high-contrast text" flag. **Principle, taken directly:** a text-on-wallpaper
widget's real legibility lever is either a (toggleable) backdrop *or* an
outline/halo around the glyph itself -- not a guess; Google shipped both
because different wallpapers need different levers. This repo's own board
feedback ("drop the background... use a soft text shadow or glow") is
exactly the second lever.

### 4. Nothing OS "Ndot"/dot-matrix clock
Nothing's brand identity widgets use a dot-matrix ("Ndot") face for clocks
and other glanceable numerals -- literally a grid of circular dots per
glyph, evoking retro LED/scoreboard displays, kept as an available style
even as Nothing OS's general UI moved its dot font in and out of the
settings-title-only role across versions. **Principle:** a dot-matrix
digit is a *procedural* glyph (a fixed on/off dot grid per character) --
cheap to draw with primitive circles, no font file needed at all, and reads
as unmistakably "digital/retro" purely from the dot grid, independent of
color.

### 5. iOS 17/18 StandBy clock styles
StandBy's full-screen clock offers several styles reachable by swiping
(Digital, Analog, Solar/World-style, Float, plus a color picker via a
long-press). Apple later brought a "Digital Clock" widget to the ordinary
Home Screen too. **Principle:** offering a *small, curated* set of
genuinely distinct styles (not a dozen minor variants) reads as more
deliberate than many options; each style earns its place by looking
different in silhouette, not just in color.

### 6. Samsung One UI lock-screen clock styles / "Adaptive Clock"
One UI 7 shipped ten lock-screen clock styles, each with its own font/size/
color controls; One UI 8's "Adaptive Clock" goes further and reflows the
numerals around whatever is in the wallpaper underneath them (a skyline, a
tree), keeping both the time and the photo visible. **Principle:** when a
clock sits directly on a photo (no backdrop, this repo's new requirement),
the strongest prior art explicitly designs the *glyph itself* to coexist
with unpredictable image content underneath -- reinforcing that a halo/
outline (or, at Samsung's extreme, actually routing the shape around
obstacles) is the load-bearing legibility mechanism once a backdrop is off
the table.

### 7. Material You (Android 12) system clock widget
Android 12's own Clock app widget ships four flavors -- Analog, Digital, a
"Stacked" two-line digital, and a dual-timezone World face -- and pulls its
color from Material You's wallpaper-derived palette rather than a fixed
brand color, so every widget matches the current wallpaper without a
person picking colors by hand. **Principle:** let the *system theme*
(here: the Omarchy/Catppuccin palette this shell already loads) supply
color, and reserve any accent for exactly one deliberate element -- Material
You's own widget style guide singles out "simple typography, scales
smoothly" as the actual design load, not novel ornamentation.

### 8. KWGT/KLWP community clock packs
The two dominant Android widget-maker apps' most-recommended clock packs in
2026 split cleanly into two families: ultra-minimal (plain numerals, huge
negative space, one accent line) and Material-You-adjacent (rounded cards,
dynamic color) -- with reviewers specifically calling out "cleaner
typography" and "adaptive designs" as what separates a good pack from a
dated one. **Principle:** restraint reads as more premium than density; the
better community packs under-decorate relative to what a first attempt
usually does.

### 9. Braun/Dieter Rams analog design language
Braun's Dieter Rams/Dietrich Lubs clocks (and Rams's own "ten principles,"
paraphrased as "as little design as possible") use Akzidenz-Grotesk (an
antecedent of Helvetica), a case with no unnecessary ornament, and a single
deliberate accent -- the second hand -- in one contrasting color against an
otherwise monochrome face; hands are conventionally photographed/set at
10:08, the most visually balanced hour on a round face. **Principle,
already partly applied in this shell's first analog attempt:** minimal tick
marks, no dial fill, one hand in the accent color and the rest in the
neutral/foreground color -- exactly Rams's "one pop of color" convention,
not a rainbow of accents.

### 10. r/unixporn desktop clock rices (Rainmeter/Conky/eww)
The Linux desktop-customization community's clock widgets (built with
Rainmeter on Windows, or Conky/eww on *nix) are typically plain, large,
monospace-or-geometric-sans numerals directly on the desktop wallpaper with
no panel background at all -- legibility usually comes from the wallpaper
itself being chosen/blurred to suit, or from a thin outline/shadow, not
from an opaque widget backdrop. **Principle, directly on point for this
board:** "no card behind the clock" is itself an established, deliberately
minimal aesthetic in this exact community, not a legibility compromise --
provided the glyph has its own contrast mechanism.

### 11. Omarchy/Hyprland desktop widget suites
Community "Omarchy desktop widgets" projects for Hyprland/Quickshell
explicitly include a "Minimal" layout described as "distraction-free...
only the centerpiece clock," a centered clock with "an expansive ambient
radial drop shadow backdrop" standing in for a panel. **Principle:** even
in a rice culture that avoids opaque cards, a *soft ambient shadow* (not a
hard-edged panel) is a recognized middle ground for legibility -- consistent
with "a soft text shadow or glow" rather than a scrim.

### 12. Teenage Engineering-adjacent minimal/industrial numeral style
(Synthesized from the Braun lineage Teenage Engineering's own product
typography descends from, rather than a separate citation -- both share
the same geometric-sans, high-restraint, single-accent lineage.) Thin
strokes, generous tracking on any accompanying label text, and numerals
that read as engineered/measured rather than playful. **Principle:** a
"thin" style should feel calm and precise -- tight but legible tracking on
the date caption underneath it, not a decorative flourish.

## Synthesis: what this change actually builds

Four styles, each earning its place by looking structurally different (not
just recolored), matching the task's ask for "Bubble / Thin / Dot matrix /
Analog":

| Style | What it borrows | How |
| --- | --- | --- |
| **Bubble** | Pixel's heavy two-line lock clock (#1), Material You's "Stacked" flavor (#7) | Centered, both lines the same very heavy weight, same color (foreground) -- no per-line color split, so the pair reads as one mass |
| **Thin** | Pixel's thin preset (#2), Braun/Teenage Engineering restraint (#9, #12) | Centered, a real thin weight (not a shrunk bold), generous tracking on the date line beneath it |
| **Dot matrix** | Nothing OS's Ndot (#4), Rainmeter/Conky's "no font dependency" ethos (#10) | A procedural 5x7 dot grid per digit, drawn with plain Cairo circles -- no font file at all, cheap every repaint |
| **Analog** | Braun/Rams's single-accent convention (#9) | No dial fill or ring (per the board's own "no dial background" ask), just tick marks and hands; the minute hand alone carries the accent color, matching Rams's one-pop-of-color rule |

And, cutting across all four (from #3's At a Glance fix and #6's Adaptive
Clock, both prior art for "no backdrop, still legible"): legibility comes
from a glow/halo computed from the *theme's own colors* -- dark numerals on
a light wallpaper get a light halo, light numerals on a dark wallpaper get
a dark halo -- rather than an opaque panel. Color use follows #7/#9's
shared rule: the theme's foreground carries most of the numeral, and the
accent is spent on exactly one element (the date caption for Bubble/Thin,
the colon for Dot matrix, the minute hand for Analog) -- never sprayed
across everything.

## Sources

- [Pixel's At a Glance just got easier to read, and I can finally use my favorite wallpaper (Android Central)](https://www.androidcentral.com/phones/google-pixel/pixels-at-a-glance-just-got-easier-to-read-and-i-can-finally-use-my-favorite-wallpaper)
- [Google's Pixel lock screen clock could become as customizable as the iPhone's (Android Police)](https://www.androidpolice.com/google-pixel-lock-screen-clock-customize-like-iphones/)
- [How to change the style or font size of the clock on the locked screen (Google Pixel Community)](https://support.google.com/pixelphone/thread/133363869/how-to-change-the-style-or-font-size-of-the-clock-on-the-locked-screen-i-hate-the-stacked-number?hl=en)
- [Nothing brings back OG 'NDot' font on Nothing OS 3.0, but there's a catch (TechIssuesToday)](https://techissuestoday.com/nothing-ndot-font-nothing-os-3-0/)
- [Nothing OS 3.0 hands-on: Dot matrix re-reloaded (Android Authority)](https://www.androidauthority.com/nothing-os-3-hands-on-3488739/)
- [How to customize StandBy in iOS 17 for the perfect full-screen experience (Macworld)](https://www.macworld.com/article/1972460/ios-17-standby-clock-widgets-photos-customize.html)
- [iOS 17.2 brings the new Digital Clock widget for the iPhone's StandBy mode and Home Screen (iDownloadBlog)](https://www.idownloadblog.com/2024/01/02/apple-ios-17-2-iphone-standby-digital-clock-widget/)
- [Here are all of One UI 7's lock screen clock styles (SamMobile)](https://www.sammobile.com/news/one-ui-7-lock-screen-clock-styles/)
- [One UI 8's Adaptive Lock Screen Clock - Explained (Sammy Fans)](https://www.sammyfans.com/2025/09/28/one-ui-8-adaptive-lock-screen-clock/)
- [Android 12 debuts its beautiful new Material You Clock widgets (Android Police)](https://www.androidpolice.com/2021/09/08/android-12-debuts-its-beautiful-new-material-you-clock-widgets/)
- [Material You design (Android Open Source Project)](https://source.android.com/docs/core/display/material)
- [12 Best KWGT Widget Packs to Customize Android Homescreen (TechPP)](https://techpp.com/2022/08/25/best-kwgt-widget-packs/)
- [10 Best KWGT Widgets for Android Customization (2026) (freedom251)](https://freedom251.com/10-best-kwgt-widgets-for-android-customization-2026/)
- [How Braun Watches' 1980s minimalism has stood the test of time (Wallpaper*)](https://www.wallpaper.com/watches-and-jewellery/how-1980s-minimalism-has-stood-the-test-of-time)
- [A History of Braun Design, Part 2: Timepieces (Core77)](https://www.core77.com/posts/24660/A-History-of-Braun-Design-Part-2-Timepieces)
- [Dieter Rams (Wikipedia)](https://en.wikipedia.org/wiki/Dieter_Rams)
- [GitHub - abduvaliy-engineer/omarchy-desktop-widgets](https://github.com/abduvaliy-engineer/omarchy-desktop-widgets)
- [Status bars – Hyprland Wiki](https://wiki.hypr.land/Useful-Utilities/Status-Bars/)
- [Inter (typeface) (Wikipedia)](https://en.wikipedia.org/wiki/Inter_(typeface))

## Font decision (feeds into `design.md`)

Checked whether a genuine variable-weight display face was usable for the
Bubble/Thin contrast this research calls for: `pango-sys` at this repo's
pinned version (0.21.5) has no binding at all for
`pango_font_description_set_variations` (confirmed with a scratch
`cargo check` against the real crate, not assumed), so the Inter *variable*
font's weight axis cannot be driven from this Rust client. `pkgs.inter`
also ships a classic **static** collection (`Inter.ttc`) with
Thin/Light/Regular/Medium/SemiBold/Bold/ExtraBold/Black as ordinary named
faces of one "Inter" family (confirmed with `fc-scan`) -- exactly what
`pango::Weight` already knows how to address the same way this shell's
existing DejaVu Book/Bold lookup works. That one file (13,172,948 bytes,
extracted alone rather than shipping all of `pkgs.inter`) is the "ONE
small... display font" this change adds, for the Clock widget only; see
`nix/shell.nix`'s own `clockDisplayFont` doc comment for the full
measurement and reasoning.
