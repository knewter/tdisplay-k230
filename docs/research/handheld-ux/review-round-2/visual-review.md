# Visual review record — 2026-10-01

Three portrait comparison sheets and a four-frame transition storyboard are
in [`visuals/`](visuals/). Each viewport retains a 568×1232 aspect ratio.
Current screenshots are embedded unchanged in the SVGs so local/site rendering
is deterministic. Each sheet captions its source and evidence class. Target
panels are labeled proposals; none is a board capture or an implementation
claim.

## Render and inspect

Rendered all four repository SVGs with librsvg on the host:

```sh
mkdir -p ~/tmp/k230-ux-review-round2-render
for f in docs/research/handheld-ux/review-round-2/visuals/*.svg; do
  rsvg-convert -o "$HOME/tmp/k230-ux-review-round2-render/$(basename "$f" .svg).png" "$f"
done
```

Inspected the resulting PNGs at full dimensions with image preview. The image
panels and storyboard annotations were legible at the rendered 1040px/620px
document width. The three screen mockups are portrait ratio and the labels
identify target versus current evidence. The current cards panel is explicitly
the older source `f39cb7eb`; it does not visually stand in for the current
candidate, whose deck capture is absent.

## Corrections from inspection

- Reduced/shortened column headings that clipped at the target panel boundary.
- Shortened the storyboard action labels so each fits its frame; preserved the
  qualification labels and the distinction between user-accepted contract,
  earlier injected board evidence, and unperformed latest-source action.
- Kept the Apps target intentionally close to the current icon-led host render:
  no added permanent controls, no extra borders, and no theme/icon changes.
  The quiet lower area is not called a defect without a populated overflow case.
- Kept the keyboard target as a behavioral contract around the existing
  handle, with no added recovery control or implied current-source reachability.
- Marked the card target as proposal-only and preserved the current-capture
  gap; static imagery is not motion evidence.

The Sheets summarize pixels, not touch. The current Apps image is a host
production-path render; cards are a prior board capture; keyboard is an older
native capture revealed by command. They cannot support same-candidate
cross-surface pixel comparisons or physical readability claims.


## Coordinator critique

The coordinator reviewed the first rendered sheets and findings on 2026-10-01.
Corrections applied: remove the card outline, replace the ambiguous “swipe up
for apps” cue with separate Overview→Home→Apps swipes, label the keyboard
frame as a prior capture, and present the accepted Home/Overview/Apps/Terminal
checks as separate paths rather than one unaccepted sequence. The findings were
also revised to treat picker overlap as optional refinement and to include the
Home clock hierarchy comparison. The coordinator agreed that tasks 2.1 and 2.3
can close with these review notes; current-journey execution and fresh physical
rechecks remain open.
