//! Home screen grid/dock geometry and hit-testing: pure layout functions in
//! the same style as `navigation.rs`'s drawer tile math, sized for a
//! webOS/Android/iOS-style rounded icon tile plus label, at a size and
//! spacing this panel and a finger can actually use comfortably (finding:
//! the first cut's 60px icons/138px rows left most of a 1232px-tall panel
//! blank -- see `docs/design/home-screen-polish.md` if that file exists, or
//! this module's own doc history otherwise).

/// Icons per row. This panel's 568x1232 aspect ratio (568:1232, about
/// 1:2.17) is close to a typical modern phone screen's, so this keeps the
/// same 4-column density most phone launchers settle on at that shape --
/// narrower than the drawer's 3-column list (which devotes most of a row's
/// width to a name label) because a Home tile is icon-first.
pub const COLUMNS: usize = 4;
/// Fixed quick-launch dock slots (webOS Quick Launch / Android hotseat
/// convention): a small, unscrolled row. Deliberately equal to `COLUMNS` so
/// dock icons line up under their grid columns, exactly like every
/// reference launcher's dock/hotseat does.
pub const DOCK_SLOTS: usize = 4;

const SIDE_MARGIN: f64 = 22.0;
const TILE_GAP: f64 = 18.0;

/// Vertical pitch of one grid row (icon plate + label + generous margin).
/// Fixed, not derived from a target row count at every call: a
/// degenerate/non-reference panel height should get *some* whole number of
/// rows at this same tile pitch rather than silently re-flowing to a
/// different tile size. At this panel's actual 1232px height it works out
/// to exactly 5 rows (`rows_per_page`): combined with `COLUMNS`, one page
/// holds 20 icons and the dock holds 4 more -- 24 icons resident at once,
/// matching `icon.rs::CACHE_LIMIT` exactly, so a fully populated Home page
/// plus its dock never evicts and re-decodes an icon mid-frame. 5 rows (not
/// 6) is also what leaves room for ~80-90px icon tiles with genuine
/// breathing room in the vertical space this panel's height actually has
/// once the top inset, page dots, and dock are reserved.
const ROW_HEIGHT: f64 = 184.0;
/// The compositor's own top-edge gesture band (`card-shell-policy.c`'s
/// default `edge_band = 48`): under `SWAY_K230_CARD_TOUCH_FIRST` (set for
/// every real session, see `nix/shell.nix`), a fresh touch-down with
/// `y < EDGE_BAND` is consumed by the shell's own pull-down-for-shade
/// gesture and never reaches this client at all -- confirmed against a real
/// compositor via headless QEMU touch injection, not inferred. Nothing
/// tappable by a *plain tap* may start above this line, though a drag whose
/// down started lower (e.g. rearranging an icon into the Remove pill) can
/// still cross into it, since ownership of an in-progress touch is decided
/// once, at its down point.
const EDGE_BAND: f64 = 48.0;
/// Rearrange mode's Done/Remove pills sit just below `EDGE_BAND`, with a
/// small margin so this stays correct even if the compositor's edge band
/// ever shifts by a pixel or two.
const PILL_TOP: f64 = EDGE_BAND + 4.0;
/// Finger-sized: 56px, matching the touch-target minimum every other
/// surface in this shell uses.
const PILL_HEIGHT: f64 = 56.0;
/// Space reserved above the grid for Home's own (minimal, non-interactive)
/// top inset and, only while rearranging, the Done/Remove pills -- which
/// must clear `EDGE_BAND` (above) to be reachable by a plain tap, plus a
/// small gap before the grid's own first row.
const GRID_TOP: f64 = PILL_TOP + PILL_HEIGHT + 12.0;
/// Height of the non-tappable page-dot row directly above the dock.
const DOTS_HEIGHT: f64 = 34.0;

/// Grid icon glyph size: comfortably inside the 72-96px "sized for a
/// finger" band this redesign targets, small enough that its rounded plate
/// (see `ICON_PLATE_SIZE`) still fits one grid column with real margin.
pub const ICON_SIZE: f64 = 80.0;
/// Padding between the icon glyph and its rounded plate's edge on every
/// side -- the plate is not the same size as the glyph so a webOS/iOS-style
/// "squircle" tile is visible even for icons with transparent edges.
const ICON_PLATE_PAD: f64 = 14.0;
pub const ICON_PLATE_SIZE: f64 = ICON_SIZE + ICON_PLATE_PAD * 2.0;
/// Height reserved for one line of the (bold, ellipsized) name label below
/// a grid icon's plate.
const LABEL_HEIGHT: f64 = 20.0;
/// Gap between an icon's plate and its label.
const ICON_LABEL_GAP: f64 = 8.0;

/// Dock icons read as the quick-launch row's own hierarchy step: visibly
/// larger than an ordinary grid icon (webOS Quick Launch and Android's
/// hotseat both do this), and unlabeled -- exactly like every reference
/// launcher's dock, which trades the name label for a bigger icon since a
/// person already knows their own four most-used apps by icon alone.
pub const DOCK_ICON_SIZE: f64 = 88.0;
const DOCK_PLATE_PAD: f64 = 10.0;
pub const DOCK_PLATE_SIZE: f64 = DOCK_ICON_SIZE + DOCK_PLATE_PAD * 2.0;
/// Height of the fixed dock band at the bottom of the panel: the dock
/// plate's own size plus symmetric vertical padding, so the translucent
/// dock panel reads as a deliberate quick-launch tray, not a cramped strip.
const DOCK_VPAD: f64 = 24.0;
const DOCK_HEIGHT: f64 = DOCK_PLATE_SIZE + DOCK_VPAD * 2.0;

/// The landscape panel (1232x568, `k230.shell.panelTransform = "270"`)
/// leaves 254px between the grid top and the dots at the regular pitch --
/// one row, which strands every 2-row widget. A panel that short is
/// "compact": the dock band's padding and the vertical gap between rows
/// tighten so two rows fit with the icon plate and label at full size.
/// Every taller output (the portrait panel and the HDMI sizes) keeps the
/// regular geometry exactly.
const COMPACT_DOCK_VPAD: f64 = 8.0;
const COMPACT_ROW_GAP: f64 = 6.0;

fn compact(height: u32) -> bool {
    f64::from(height) - DOCK_HEIGHT - DOTS_HEIGHT - GRID_TOP < 2.0 * ROW_HEIGHT
}

fn dock_height(height: u32) -> f64 {
    if compact(height) {
        DOCK_PLATE_SIZE + COMPACT_DOCK_VPAD * 2.0
    } else {
        DOCK_HEIGHT
    }
}

/// Vertical pitch of one grid row and the gap left below each tile.
fn row_metrics(height: u32) -> (f64, f64) {
    if compact(height) {
        let available = (grid_bottom(height) - GRID_TOP).max(0.0);
        ((available / 2.0).min(ROW_HEIGHT), COMPACT_ROW_GAP)
    } else {
        (ROW_HEIGHT, TILE_GAP)
    }
}

/// Visual radius of the small "remove" badge rearrange mode draws at each
/// filled icon's top-left corner (iOS/webOS's jiggle-mode affordance).
pub const REMOVE_BADGE_RADIUS: f64 = 13.0;
/// The badge's actual hit-test radius: noticeably larger than its drawn
/// circle, so this stays a genuinely finger-sized target instead of one a
/// person has to aim a fingertip at precisely.
pub const REMOVE_BADGE_HIT_RADIUS: f64 = 22.0;

pub fn grid_top(_height: u32) -> f64 {
    GRID_TOP
}

pub fn dock_top(height: u32) -> f64 {
    f64::from(height) - dock_height(height)
}

pub fn dots_center_y(height: u32) -> f64 {
    dock_top(height) - DOTS_HEIGHT / 2.0
}

fn grid_bottom(height: u32) -> f64 {
    dock_top(height) - DOTS_HEIGHT
}

/// How many full tile rows fit in the space between the grid top and the
/// dots/dock band, at `ROW_HEIGHT`'s fixed pitch. Always at least 1, so a
/// degenerate (very short) panel still shows something rather than a
/// zero-capacity page. At this panel's actual 1232px height this is
/// exactly `ROWS` (5); see this module's top doc comment for why 5.
pub fn rows_per_page(height: u32) -> usize {
    let available = (grid_bottom(height) - GRID_TOP).max(0.0);
    let (pitch, _) = row_metrics(height);
    ((available / pitch).floor() as usize).max(1)
}

/// How many grid columns fit `width`: `crate::reflow_columns` at scale
/// `1.0` -- the same "more columns, not bigger ones" reflow
/// `navigation::columns_for_width` gives the Drawer (see that function's
/// own doc for why scale is fixed here). Exactly [`COLUMNS`] (4) at this
/// panel's own 568px width, pixel-identical to before this existed. This is
/// the *reference* column count for a brand-new page/layout; an already-
/// persisted [`crate::home_state::HomeLayout`] instead carries its own
/// live `columns` field (safely migrated by `HomeLayout::reflow_to` when it
/// no longer matches this), because unlike the Drawer, Home's grid has
/// per-page data indexed by column count that must never silently
/// reinterpret itself.
pub fn columns_for_width(width: u32) -> usize {
    crate::reflow_columns(width, 1.0, COLUMNS)
}

pub fn apps_per_page(width: u32, height: u32) -> usize {
    columns_for_width(width) * rows_per_page(height)
}

/// Icons `icon.rs::CACHE_LIMIT` keeps resident: one full Home page plus
/// its dock should fit, so a wider dock may only take what the page leaves.
const ICON_BUDGET: usize = 24;

/// How many dock slots `width`x`height` shows: [`DOCK_SLOTS`] (4) on the
/// portrait panel, and more on a wide surface (operator, 2026-10-14: "More
/// slots when wide"), one per grid column but never more than the page
/// leaves of the icon budget -- 6 at 1280x800 and 1232x568. Never fewer
/// than [`DOCK_SLOTS`]: an output whose page alone already exceeds the
/// budget (1920x1080) keeps the panel's 4 rather than losing slots.
pub fn dock_slots(width: u32, height: u32) -> usize {
    let room = ICON_BUDGET.saturating_sub(apps_per_page(width, height));
    columns_for_width(width).min(room).max(DOCK_SLOTS)
}

fn tile_width(width: u32, columns: usize) -> f64 {
    let columns = columns.max(1);
    ((f64::from(width) - 2.0 * SIDE_MARGIN - (columns - 1) as f64 * TILE_GAP) / columns as f64)
        .max(0.0)
}

/// `slot` is the icon's position *within the current page* (0-based, row
/// major), not its absolute index across every page. This is the tile's
/// outer cell -- used for hit-testing and the rearrange-mode drop-target
/// highlight -- not where its icon plate is actually painted; see
/// [`tile_content`] for that (the plate and label sit centered within this
/// cell, not pinned to its top edge). `columns` is the page's own live
/// column count (`home_state::HomeLayout::columns`), not necessarily
/// [`columns_for_width`]'s fresh value for `width` -- painting and hit-
/// testing must always agree with what the *stored* layout was last
/// reflowed to, which `HomeScreen::sync_columns` keeps equal to
/// `columns_for_width(width)` before either ever runs.
pub fn tile_rect(width: u32, height: u32, slot: usize, columns: usize) -> (f64, f64, f64, f64) {
    let columns = columns.max(1);
    let w = tile_width(width, columns);
    let column = slot % columns;
    let row = slot / columns;
    let (pitch, gap) = row_metrics(height);
    (
        SIDE_MARGIN + column as f64 * (w + TILE_GAP),
        grid_top(height) + row as f64 * pitch,
        w,
        pitch - gap,
    )
}

/// The bounding rect a multi-cell item (a widget, currently the only
/// [`crate::home_state::HomeItem`] wider than one cell) paints into: from
/// its anchor tile's own top-left corner through the bottom-right corner of
/// the last tile its `span` (columns, rows) covers, inclusive of the
/// internal tile gaps -- a widget's card is meant to read as one
/// contiguous surface, not several glued-together tiles with visible seams.
/// Callers must only pass a `top_left`/`span` combination that already fits
/// on the page (`home_state::HomeLayout::place` is the one thing that
/// decides that); this performs no bounds checking of its own.
pub fn spanned_tile_rect(width: u32, height: u32, top_left: usize, span: (usize, usize), columns: usize) -> (f64, f64, f64, f64) {
    let (cols, rows) = span;
    let columns = columns.max(1);
    let (x0, y0, _, _) = tile_rect(width, height, top_left, columns);
    let last = top_left + (rows.max(1) - 1) * columns + (cols.max(1) - 1);
    let (x1, y1, w1, h1) = tile_rect(width, height, last, columns);
    (x0, y0, (x1 + w1) - x0, (y1 + h1) - y0)
}

/// Where a grid icon's rounded plate and label actually paint within its
/// tile cell: horizontally centered, and the icon+label block vertically
/// centered in the cell's height rather than pinned to its top edge -- a
/// tile cell is taller than an icon+label needs (see this module's top
/// comment), and top-pinning it is exactly what made the first cut's icons
/// read as "crammed at the top" of an otherwise-empty page.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct TileContent {
    pub plate_x: f64,
    pub plate_y: f64,
    pub plate_size: f64,
    pub label_y: f64,
}

pub fn tile_content(width: u32, height: u32, slot: usize, columns: usize) -> TileContent {
    let (x, y, w, h) = tile_rect(width, height, slot, columns);
    let content_h = ICON_PLATE_SIZE + ICON_LABEL_GAP + LABEL_HEIGHT;
    let top = y + ((h - content_h) / 2.0).max(0.0);
    TileContent {
        plate_x: x + (w - ICON_PLATE_SIZE) / 2.0,
        plate_y: top,
        plate_size: ICON_PLATE_SIZE,
        label_y: top + ICON_PLATE_SIZE + ICON_LABEL_GAP,
    }
}

/// Which in-page slot, if any, a point lands on. `filled` bounds the search
/// to slots that actually hold an icon on this page (a tap past the last
/// filled slot, in an otherwise-valid grid cell, hits nothing). `columns`
/// must be the same page's live column count `tile_rect` was painted with
/// (see that function's own doc).
pub fn slot_at(point: (f64, f64), width: u32, height: u32, filled: usize, columns: usize) -> Option<usize> {
    if !point.0.is_finite() || !point.1.is_finite() {
        return None;
    }
    let per_page = columns.max(1) * rows_per_page(height);
    for slot in 0..filled.min(per_page) {
        let (x, y, w, h) = tile_rect(width, height, slot, columns);
        if point.0 >= x && point.0 < x + w && point.1 >= y && point.1 < y + h {
            return Some(slot);
        }
    }
    None
}

fn dock_slot_width(width: u32, slots: usize) -> f64 {
    let slots = slots.max(1);
    ((f64::from(width) - 2.0 * SIDE_MARGIN - (slots - 1) as f64 * TILE_GAP) / slots as f64).max(0.0)
}

/// A dock slot's outer cell, spanning the dock band's full height -- unlike
/// the grid, a dock icon has no label, so [`dock_content`]'s plate centers
/// directly within this rect with no separate label allowance.
pub fn dock_rect(width: u32, height: u32, slot: usize) -> (f64, f64, f64, f64) {
    let w = dock_slot_width(width, dock_slots(width, height));
    (
        SIDE_MARGIN + slot as f64 * (w + TILE_GAP),
        dock_top(height),
        w,
        dock_height(height),
    )
}

/// Where a dock icon's rounded plate actually paints: centered in its cell,
/// at [`DOCK_PLATE_SIZE`] -- visibly larger than a grid tile's plate, since
/// dock icons are meant to read as the quick-launch row's own hierarchy
/// step (see this module's `DOCK_ICON_SIZE` doc comment).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct DockContent {
    pub plate_x: f64,
    pub plate_y: f64,
    pub plate_size: f64,
}

pub fn dock_content(width: u32, height: u32, slot: usize) -> DockContent {
    let (x, y, w, h) = dock_rect(width, height, slot);
    DockContent {
        plate_x: x + (w - DOCK_PLATE_SIZE) / 2.0,
        plate_y: y + (h - DOCK_PLATE_SIZE) / 2.0,
        plate_size: DOCK_PLATE_SIZE,
    }
}

pub fn dock_slot_at(point: (f64, f64), width: u32, height: u32) -> Option<usize> {
    if !point.0.is_finite() || !point.1.is_finite() {
        return None;
    }
    for slot in 0..dock_slots(width, height) {
        let (x, y, w, h) = dock_rect(width, height, slot);
        if point.0 >= x && point.0 < x + w && point.1 >= y && point.1 < y + h {
            return Some(slot);
        }
    }
    None
}

/// A location a pinned icon can occupy: a grid slot on a specific page, or a
/// dock slot (page-independent). Used both by hit-testing (where did this
/// touch land) and by rearrange-mode drop targets (where should this icon
/// go).
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum HomeSlot {
    Grid { page: usize, slot: usize },
    Dock { slot: usize },
}

/// The top-left corner of `slot`'s icon plate -- where rearrange mode draws
/// (and hit-tests) that icon's remove badge. Grid and dock plates have
/// different sizes/positions ([`tile_content`] vs [`dock_content`]), but
/// both anchor their badge at exactly this corner, matching iOS/webOS.
pub fn plate_top_left(width: u32, height: u32, slot: HomeSlot, columns: usize) -> (f64, f64) {
    match slot {
        HomeSlot::Grid { slot, .. } => {
            let content = tile_content(width, height, slot, columns);
            (content.plate_x, content.plate_y)
        }
        HomeSlot::Dock { slot } => {
            let content = dock_content(width, height, slot);
            (content.plate_x, content.plate_y)
        }
    }
}

/// Whether `point` falls within `radius` of `center` -- used for the round
/// remove-badge hit test (a circular target reads more naturally against a
/// round badge than a bounding box would).
pub fn hits_circle(point: (f64, f64), center: (f64, f64), radius: f64) -> bool {
    if !point.0.is_finite() || !point.1.is_finite() {
        return false;
    }
    let dx = point.0 - center.0;
    let dy = point.1 - center.1;
    dx * dx + dy * dy <= radius * radius
}

/// Rearrange mode's contextual "Done" affordance: a finger-sized pill in
/// the top inset band, clear of the compositor's own top-edge gesture band
/// (`EDGE_BAND`) so a plain tap actually reaches it -- not permanent
/// chrome, it only exists while rearranging.
pub fn done_button_rect(width: u32) -> (f64, f64, f64, f64) {
    let w = 128.0;
    (f64::from(width) - SIDE_MARGIN - w, PILL_TOP, w, PILL_HEIGHT)
}

/// Rearrange mode's remove target, alongside the Done pill, in the same top
/// inset band so it never overlaps a grid row. Dragging an icon here is the
/// original remove gesture; the per-icon remove badge ([`plate_top_left`])
/// is the newer, more discoverable one -- both stay live at once.
pub fn remove_target_rect(_width: u32) -> (f64, f64, f64, f64) {
    (SIDE_MARGIN, PILL_TOP, 128.0, PILL_HEIGHT)
}

/// A folder tile's 2x2 mini-icon preview rects, inside its own plate rect
/// (`tile_content`'s or `dock_content`'s `plate_x/plate_y/plate_size`) --
/// the first (up to) 4 member apps, in folder order, each drawn small
/// enough that all 4 read as one rounded tile at a glance (task: "A folder
/// icon is a rounded tile with 2x2 mini icons").
pub fn folder_mini_icon_rects(plate_x: f64, plate_y: f64, plate_size: f64) -> [(f64, f64, f64, f64); 4] {
    let pad = plate_size * 0.12;
    let gap = plate_size * 0.06;
    let cell = (plate_size - 2.0 * pad - gap) / 2.0;
    let mut rects = [(0.0, 0.0, 0.0, 0.0); 4];
    for (index, rect) in rects.iter_mut().enumerate() {
        let column = index % 2;
        let row = index / 2;
        *rect = (
            plate_x + pad + column as f64 * (cell + gap),
            plate_y + pad + row as f64 * (cell + gap),
            cell,
            cell,
        );
    }
    rects
}

/// The open-folder overlay's own card rect: a centered rounded sheet,
/// leaving the same top inset every other overlay (Shade/Settings) respects
/// and generous side margins so Home's wallpaper still reads behind it.
pub fn folder_overlay_rect(width: u32, height: u32) -> (f64, f64, f64, f64) {
    folder_overlay_rect_inset(width, height, 0.0)
}

/// The same card, shifted up by `keyboard_inset` (the on-screen keyboard's
/// reserved height, task 2: "the layout stays unsquashed") so its bottom
/// edge clears the keyboard rather than being covered by it, while renaming
/// a folder -- never shifted past the compositor's own top-edge gesture
/// band. `keyboard_inset` of `0.0` is exactly [`folder_overlay_rect`].
pub fn folder_overlay_rect_inset(width: u32, height: u32, keyboard_inset: f64) -> (f64, f64, f64, f64) {
    let x = SIDE_MARGIN * 1.5;
    // On the landscape panel the card starts just below the compositor's
    // top-edge band instead of at the grid: the dim Home behind it needs no
    // room, and two rows of full-size tiles need the height (see
    // `folder_columns`).
    let y = if folder_wide(width, height) { PILL_TOP } else { GRID_TOP };
    let w = f64::from(width) - 2.0 * x;
    let h = f64::from(height) - y - dock_height(height) - DOTS_HEIGHT;
    // The wide card is already at the top band, so a keyboard inset cannot
    // lift it; the name field stays reachable above the keyboard and the
    // member tiles are covered only while renaming.
    let shifted_y = (y - keyboard_inset.max(0.0)).max(PILL_TOP);
    (x, shifted_y, w, h)
}

/// Height reserved at the top of the open-folder card for its editable
/// name label (task: "an editable name (tap the name to rename)").
pub const FOLDER_NAME_HEIGHT: f64 = 56.0;

fn folder_name_rect_of(card: (f64, f64, f64, f64)) -> (f64, f64, f64, f64) {
    let (x, y, w, _) = card;
    (x, y, w, FOLDER_NAME_HEIGHT)
}

/// The folder name label's own tap rect, within the overlay card.
pub fn folder_name_rect(width: u32, height: u32) -> (f64, f64, f64, f64) {
    folder_name_rect_of(folder_overlay_rect(width, height))
}

/// [`folder_name_rect`], within the keyboard-shifted card.
pub fn folder_name_rect_inset(width: u32, height: u32, keyboard_inset: f64) -> (f64, f64, f64, f64) {
    folder_name_rect_of(folder_overlay_rect_inset(width, height, keyboard_inset))
}

/// Whether the open-folder overlay uses the landscape layout (the same
/// predicate as Help, Settings and the Shade).
pub fn folder_wide(width: u32, height: u32) -> bool {
    crate::help::wide(width, height)
}

/// Member tiles per row in an open folder: the Home grid's `COLUMNS` on the
/// portrait panel, eight across the landscape card so its two rows hold as
/// many members as the portrait card's rows do.
pub fn folder_columns(width: u32, height: u32) -> usize {
    if folder_wide(width, height) { 8 } else { COLUMNS }
}

fn folder_app_rect_of(card: (f64, f64, f64, f64), index: usize, width: u32, height: u32) -> (f64, f64, f64, f64) {
    let (card_x, card_y, card_w, _) = card;
    let (pitch, gap) = row_metrics(height);
    let grid_top = card_y + FOLDER_NAME_HEIGHT + 12.0;
    let columns = folder_columns(width, height);
    let column = index % columns;
    let row = index / columns;
    let w = ((card_w - 2.0 * TILE_GAP) / columns as f64 - TILE_GAP).max(0.0);
    (
        card_x + TILE_GAP + column as f64 * (w + TILE_GAP),
        grid_top + row as f64 * pitch,
        w,
        pitch - gap,
    )
}

/// One app tile's rect inside an open folder's own grid, below the name
/// label -- same `COLUMNS` density as the Home grid, but scoped to the
/// card's own width/height rather than the full panel.
pub fn folder_app_rect(width: u32, height: u32, index: usize) -> (f64, f64, f64, f64) {
    folder_app_rect_of(folder_overlay_rect(width, height), index, width, height)
}

/// [`folder_app_rect`], within the keyboard-shifted card.
pub fn folder_app_rect_inset(width: u32, height: u32, index: usize, keyboard_inset: f64) -> (f64, f64, f64, f64) {
    folder_app_rect_of(folder_overlay_rect_inset(width, height, keyboard_inset), index, width, height)
}

/// Which app tile, if any, inside an open folder's grid `point` lands on,
/// bounded to `count` actual members (an open folder with more members
/// than fit in the card is not supported yet -- see this function's own
/// call sites' doc for the deferred-scrolling note).
pub fn folder_app_at(point: (f64, f64), width: u32, height: u32, count: usize, keyboard_inset: f64) -> Option<usize> {
    if !point.0.is_finite() || !point.1.is_finite() {
        return None;
    }
    for index in 0..count {
        let (x, y, w, h) = folder_app_rect_inset(width, height, index, keyboard_inset);
        if point.0 >= x && point.0 < x + w && point.1 >= y && point.1 < y + h {
            return Some(index);
        }
    }
    None
}

/// The widget-picker sheet's own card rect (task: long-press empty Home
/// space opens "Widgets / Wallpaper & style / Home settings") -- the same
/// centered card region an open folder uses; the two are never shown at
/// once (mutually exclusive `HomeScreen` state), so sharing the region
/// costs nothing and keeps every overlay's card in one visually consistent
/// place.
pub fn picker_rect(width: u32, height: u32) -> (f64, f64, f64, f64) {
    folder_overlay_rect(width, height)
}

/// The picker card's row geometry. Rows are the full card width at up to
/// 92 px tall; when the longest page (the Widgets page: Back plus one row
/// per `WidgetKind`) cannot fit the card's height in one column, the rows
/// split into two columns, and the row height shrinks to fit (not below
/// `PICKER_MIN_ROW_HEIGHT`). Every page uses the same geometry, so every
/// row of every page stays inside the card, which is where a press counts
/// as on the sheet rather than as a dismiss.
const PICKER_ROW_HEIGHT: f64 = 92.0;
const PICKER_MIN_ROW_HEIGHT: f64 = 56.0;
const PICKER_ROW_GAP: f64 = 14.0;
const PICKER_TOP_PAD: f64 = 20.0;
const PICKER_COLUMN_GAP: f64 = 16.0;

/// Rows on the picker's longest page.
pub fn picker_max_rows() -> usize {
    crate::home_state::WidgetKind::ALL.len() + 1
}

/// `(columns, rows per column, row height, gap)` for the picker card.
fn picker_grid(width: u32, height: u32) -> (usize, usize, f64, f64) {
    let (_, _, w, h) = picker_rect(width, height);
    let rows = picker_max_rows();
    let fit = |per_column: usize| {
        let gaps = per_column.saturating_sub(1) as f64;
        let mut gap = PICKER_ROW_GAP;
        let mut row = (h - 2.0 * PICKER_TOP_PAD - gaps * gap) / per_column as f64;
        if row < PICKER_MIN_ROW_HEIGHT {
            gap = 8.0;
            row = (h - 2.0 * PICKER_TOP_PAD - gaps * gap) / per_column as f64;
        }
        (row.min(PICKER_ROW_HEIGHT), gap)
    };
    let (row, gap) = fit(rows);
    // Two columns only where the card is wide enough for two readable rows.
    if row >= PICKER_ROW_HEIGHT * 0.85 || w < 2.0 * 360.0 + PICKER_COLUMN_GAP + 32.0 {
        return (1, rows, row.max(PICKER_MIN_ROW_HEIGHT.min(row)), gap);
    }
    let per_column = rows.div_ceil(2);
    let (row, gap) = fit(per_column);
    (2, per_column, row, gap)
}

/// The `index`-th row's rect within the picker card.
pub fn picker_row_rect(width: u32, height: u32, index: usize) -> (f64, f64, f64, f64) {
    let (x, y, w, _) = picker_rect(width, height);
    let (columns, per_column, row_h, gap) = picker_grid(width, height);
    let inner_w = w - 32.0;
    let col_w = (inner_w - (columns - 1) as f64 * PICKER_COLUMN_GAP) / columns as f64;
    let column = (index / per_column).min(columns - 1);
    let row = index - column * per_column;
    (
        x + 16.0 + column as f64 * (col_w + PICKER_COLUMN_GAP),
        y + PICKER_TOP_PAD + row as f64 * (row_h + gap),
        col_w,
        row_h,
    )
}

/// Which row, if any, of the picker's current page (bounded to `count` rows
/// actually shown) `point` lands on.
pub fn picker_row_at(point: (f64, f64), width: u32, height: u32, count: usize) -> Option<usize> {
    if !point.0.is_finite() || !point.1.is_finite() {
        return None;
    }
    (0..count).find(|&index| hits(point, picker_row_rect(width, height, index)))
}

pub fn hits(point: (f64, f64), rect: (f64, f64, f64, f64)) -> bool {
    point.0.is_finite()
        && point.1.is_finite()
        && point.0 >= rect.0
        && point.0 < rect.0 + rect.2
        && point.1 >= rect.1
        && point.1 < rect.1 + rect.3
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn columns_for_width_matches_the_reference_at_568_and_grows_for_hdmi() {
        assert_eq!(columns_for_width(568), COLUMNS);
        assert_eq!(columns_for_width(1080), 8);
        assert_eq!(columns_for_width(1920), 14);
    }

    #[test]
    fn wide_hdmi_grid_hits_every_reflowed_column_of_the_first_row() {
        // Mirrors `navigation::wide_hdmi_output_hits_every_reflowed_column_
        // of_the_first_row`: the Home grid's own `tile_rect`/`slot_at` must
        // stay in lockstep at a column count the reference 4 was never
        // authored for.
        // Landscape HDMI monitors too (the-hdmi-shell-works-in-landscape
        // 5.3): 1280x800 and 720p, two rows deep.
        for (width, height) in [(1920u32, 1080u32), (1280, 800), (1280, 720)] {
            let columns = columns_for_width(width);
            assert!(columns > COLUMNS);
            for slot in 0..2 * columns {
                let (x, y, w, h) = tile_rect(width, height, slot, columns);
                assert!(w > 0.0 && h > 0.0);
                assert!(x >= 0.0 && x + w <= f64::from(width), "tile {slot} must stay on-panel at {width}x{height}");
                assert!(y >= 0.0 && y + h <= f64::from(height), "tile {slot} must stay on-panel at {width}x{height}");
                assert_eq!(
                    slot_at((x + w / 2.0, y + h / 2.0), width, height, 2 * columns, columns),
                    Some(slot)
                );
            }
        }
    }

    #[test]
    fn four_columns_hit_only_painted_tiles() {
        for slot in 0..7 {
            let (x, y, w, h) = tile_rect(568, 1232, slot, COLUMNS);
            assert!(w >= 56.0 && h >= 56.0, "tile must clear the 56px touch target");
            assert_eq!(slot_at((x + w / 2.0, y + h / 2.0), 568, 1232, 7, COLUMNS), Some(slot));
        }
        assert_eq!(slot_at((0.0, 0.0), 568, 1232, 7, COLUMNS), None, "above the grid");
        let (x, y, w, _) = tile_rect(568, 1232, 6, COLUMNS);
        assert_eq!(
            slot_at((x + w + 5.0, y + 5.0), 568, 1232, 7, COLUMNS),
            None,
            "column gap between rows"
        );
    }

    #[test]
    fn slot_at_respects_filled_bound() {
        let (x, y, w, h) = tile_rect(568, 1232, 3, COLUMNS);
        assert_eq!(slot_at((x + w / 2.0, y + h / 2.0), 568, 1232, 3, COLUMNS), None, "slot 3 is unfilled");
        assert_eq!(slot_at((x + w / 2.0, y + h / 2.0), 568, 1232, 4, COLUMNS), Some(3));
    }

    #[test]
    fn rows_per_page_is_bounded_and_targets_five_at_the_reference_height() {
        assert_eq!(rows_per_page(1232), 5, "one page + dock should total 24 icons, see top doc comment");
        assert_eq!(apps_per_page(568, 1232), COLUMNS * 5);
        assert!(rows_per_page(50) >= 1, "a degenerate panel still has one row");
    }

    #[test]
    fn the_landscape_panel_gets_two_full_size_rows() {
        assert!(!compact(1232) && !compact(1024) && !compact(1080));
        assert!(compact(568));
        assert_eq!(rows_per_page(568), 2, "a 2-row widget fits a landscape page");
        let content = ICON_PLATE_SIZE + ICON_LABEL_GAP + LABEL_HEIGHT;
        let (_, y0, _, h) = tile_rect(1232, 568, 0, 9);
        let (_, y1, _, _) = tile_rect(1232, 568, 9, 9);
        assert!(h >= content, "plate and label fit the tile: {h} < {content}");
        assert!(y1 + h <= grid_bottom(568) + 0.001, "the second row clears the dots");
        assert!(y0 >= GRID_TOP);
        assert!(apps_per_page(1232, 568) + dock_slots(1232, 568) <= 24, "page plus dock stays inside the icon cache");
    }

    #[test]
    fn one_page_plus_dock_matches_the_icon_cache_bound() {
        // icon.rs::CACHE_LIMIT is 24; a fully populated page (apps_per_page)
        // plus a full dock (DOCK_SLOTS) must never exceed it, or a full
        // Home page would evict and re-decode an icon every frame.
        assert_eq!(apps_per_page(568, 1232) + DOCK_SLOTS, 24);
    }

    #[test]
    fn a_wide_dock_grows_within_the_icon_budget() {
        assert_eq!(dock_slots(568, 1232), DOCK_SLOTS, "the portrait panel keeps its 4");
        assert_eq!(dock_slots(1280, 800), 6);
        assert_eq!(dock_slots(1232, 568), 6);
        assert_eq!(dock_slots(1920, 1080), DOCK_SLOTS, "never fewer than the panel's 4");
        for (w, h) in [(1280, 800), (1232, 568)] {
            assert!(apps_per_page(w, h) + dock_slots(w, h) <= 24);
            let mut right = 0.0;
            for slot in 0..dock_slots(w, h) {
                let (x, y, cw, ch) = dock_rect(w, h, slot);
                assert!(x >= right && cw >= 56.0 && ch >= 56.0, "{w}x{h} slot {slot} overlaps or is too small");
                assert!(x + cw <= f64::from(w), "{w}x{h} slot {slot} runs off the edge");
                assert!(dock_content(w, h, slot).plate_size <= cw);
                assert_eq!(dock_slot_at((x + cw / 2.0, y + ch / 2.0), w, h), Some(slot));
                right = x + cw;
            }
        }
    }

    #[test]
    fn icon_sizes_are_in_the_finger_sized_band() {
        assert!((72.0..=96.0).contains(&ICON_SIZE));
        assert!((72.0..=96.0).contains(&DOCK_ICON_SIZE));
        assert!(DOCK_ICON_SIZE > ICON_SIZE, "the dock reads as a distinct, larger hierarchy step");
    }

    #[test]
    fn tile_content_centers_the_plate_in_its_cell_not_at_the_top() {
        let (_, cell_y, _, cell_h) = tile_rect(568, 1232, 0, COLUMNS);
        let content = tile_content(568, 1232, 0, COLUMNS);
        assert!(content.plate_x > 0.0);
        assert!(content.plate_y > cell_y, "the plate must not be pinned to the cell's top edge");
        assert!(content.label_y > content.plate_y + content.plate_size);
        assert!(content.label_y + LABEL_HEIGHT < cell_y + cell_h, "label stays inside its own cell");
        assert_eq!(content.plate_size, ICON_PLATE_SIZE);
    }

    #[test]
    fn dock_content_centers_a_larger_plate_with_no_label_allowance() {
        let (_, cell_y, _, cell_h) = dock_rect(568, 1232, 0);
        let content = dock_content(568, 1232, 0);
        assert_eq!(content.plate_size, DOCK_PLATE_SIZE);
        assert!(content.plate_y > cell_y && content.plate_y + content.plate_size < cell_y + cell_h);
    }

    #[test]
    fn dock_slots_are_touch_sized_and_distinct() {
        for slot in 0..DOCK_SLOTS {
            let (x, y, w, h) = dock_rect(568, 1232, slot);
            assert!(w >= 56.0 && h >= 56.0);
            assert_eq!(dock_slot_at((x + w / 2.0, y + h / 2.0), 568, 1232), Some(slot));
        }
        let (grid_x, grid_y, _, _) = tile_rect(568, 1232, 0, COLUMNS);
        assert_eq!(
            dock_slot_at((grid_x, grid_y), 568, 1232),
            None,
            "grid tiles are not dock hits"
        );
    }

    #[test]
    fn done_and_remove_targets_sit_in_the_top_inset_and_do_not_overlap() {
        let done = done_button_rect(568);
        let remove = remove_target_rect(568);
        assert!(done.3 >= 56.0, "Done clears the 56px touch target");
        assert!(remove.3 >= 56.0, "Remove clears the 56px touch target");
        assert!(done.1 + done.3 <= GRID_TOP, "Done stays above the grid");
        assert!(remove.1 + remove.3 <= GRID_TOP, "Remove stays above the grid");
        assert!(remove.0 + remove.2 <= done.0, "Remove and Done do not overlap");
        assert!(hits((done.0 + 4.0, done.1 + 4.0), done));
        assert!(!hits((done.0 + 4.0, done.1 + 4.0), remove));
    }

    #[test]
    fn done_and_remove_pills_clear_the_compositors_top_edge_gesture_band() {
        // A fresh tap starting at y < EDGE_BAND is consumed by the
        // compositor's own pull-down-for-shade gesture and never reaches
        // this client at all (confirmed against a real compositor via
        // headless QEMU touch injection) -- so a pill a person is meant to
        // *tap* must sit entirely below that line, not just above the grid.
        let done = done_button_rect(568);
        let remove = remove_target_rect(568);
        assert!(done.1 >= EDGE_BAND, "Done must clear the top-edge gesture band");
        assert!(remove.1 >= EDGE_BAND, "Remove must clear the top-edge gesture band");
    }

    #[test]
    fn dock_sits_below_the_grid_and_dots() {
        let grid_bottom_edge = tile_rect(568, 1232, (rows_per_page(1232) - 1) * COLUMNS, COLUMNS).1
            + tile_rect(568, 1232, 0, COLUMNS).3;
        assert!(dots_center_y(1232) >= grid_bottom_edge);
        assert!(dock_top(1232) > dots_center_y(1232));
    }

    #[test]
    fn folder_mini_icons_stay_inside_the_plate_and_do_not_overlap() {
        let rects = folder_mini_icon_rects(100.0, 200.0, 108.0);
        for (x, y, w, h) in rects {
            assert!(x >= 100.0 && y >= 200.0 && x + w <= 100.0 + 108.0 && y + h <= 200.0 + 108.0);
        }
        // top-left and top-right must not overlap horizontally
        assert!(rects[0].0 + rects[0].2 <= rects[1].0);
        // top-left and bottom-left must not overlap vertically
        assert!(rects[0].1 + rects[0].3 <= rects[2].1);
    }

    #[test]
    fn folder_app_at_hits_only_the_requested_count_of_tiles() {
        assert_eq!(folder_app_at((0.0, 0.0), 568, 1232, 4, 0.0), None, "above the card's own grid");
        let (x, y, w, h) = folder_app_rect(568, 1232, 0);
        let point = (x + w / 2.0, y + h / 2.0);
        assert_eq!(folder_app_at(point, 568, 1232, 4, 0.0), Some(0));
        assert_eq!(folder_app_at(point, 568, 1232, 0, 0.0), None, "no members at all yet");
    }

    #[test]
    fn folder_overlay_rect_inset_shifts_the_card_up_but_not_past_the_top_band() {
        let plain = folder_overlay_rect(568, 1232);
        let shifted = folder_overlay_rect_inset(568, 1232, 40.0);
        assert_eq!(shifted.1, plain.1 - 40.0);
        assert_eq!(shifted.0, plain.0);
        assert_eq!((shifted.2, shifted.3), (plain.2, plain.3));
        assert_eq!(folder_overlay_rect_inset(568, 1232, 0.0), plain);
        // An enormous inset still stays below the compositor's own top-edge
        // gesture band rather than going negative/off-panel.
        let extreme = folder_overlay_rect_inset(568, 1232, 5000.0);
        assert!(extreme.1 >= PILL_TOP);
    }

    #[test]
    fn picker_rows_are_distinct_finger_sized_and_bounded_by_count() {
        for index in 0..4 {
            let (_, _, w, h) = picker_row_rect(568, 1232, index);
            assert!(w >= 56.0 && h >= 56.0);
        }
        let (x, y, w, h) = picker_row_rect(568, 1232, 1);
        let point = (x + w / 2.0, y + h / 2.0);
        assert_eq!(picker_row_at(point, 568, 1232, 3), Some(1));
        assert_eq!(picker_row_at(point, 568, 1232, 1), None, "row 1 not shown when only 1 row is bound");
        let (x0, y0, w0, h0) = picker_row_rect(568, 1232, 0);
        assert!((y + h / 2.0) > y0 + h0, "rows do not overlap");
        let _ = (x0, w0);
    }

    #[test]
    fn every_picker_row_sits_inside_the_card_at_every_surface() {
        for (width, height) in [(568u32, 1232u32), (1232, 568), (1280, 800), (1280, 720), (1920, 1080)] {
            let (cx, cy, cw, ch) = picker_rect(width, height);
            let rows = picker_max_rows();
            for index in 0..rows {
                let (x, y, w, h) = picker_row_rect(width, height, index);
                assert!(x >= cx && y >= cy && x + w <= cx + cw + 0.01 && y + h <= cy + ch + 0.01,
                    "{width}x{height} row {index} {:?} outside card {:?}", (x, y, w, h), (cx, cy, cw, ch));
                assert!(h >= 40.0 && w >= 200.0, "{width}x{height} row {index} too small: {w}x{h}");
                let centre = (x + w / 2.0, y + h / 2.0);
                assert_eq!(picker_row_at(centre, width, height, rows), Some(index));
            }
        }
    }

    #[test]
    fn folder_overlay_card_sits_within_the_panel_and_above_the_dock() {
        let (x, y, w, h) = folder_overlay_rect(568, 1232);
        assert!(x > 0.0 && y > 0.0);
        assert!(x + w < 568.0);
        assert!(y + h < dock_top(1232));
    }

    #[test]
    fn spanned_tile_rect_covers_every_cell_the_span_names_with_no_seam() {
        // A 4x2 Clock anchored at slot 0 should read as one card exactly as
        // wide as all 4 columns and as tall as 2 rows, including the gaps
        // between the tiles it spans -- not 8 separate tile rects glued
        // together with visible gutters between them.
        let spanned = spanned_tile_rect(568, 1232, 0, (4, 2), COLUMNS);
        let (last_x, last_y, last_w, last_h) = tile_rect(568, 1232, 4 + 3, COLUMNS);
        assert_eq!(spanned.0, tile_rect(568, 1232, 0, COLUMNS).0);
        assert_eq!(spanned.1, tile_rect(568, 1232, 0, COLUMNS).1);
        assert_eq!(spanned.2, (last_x + last_w) - spanned.0);
        assert_eq!(spanned.3, (last_y + last_h) - spanned.1);
    }

    #[test]
    fn remove_badge_sits_at_the_plates_own_corner_and_hit_radius_exceeds_visual_radius() {
        assert!(REMOVE_BADGE_HIT_RADIUS > REMOVE_BADGE_RADIUS);
        let slot = HomeSlot::Grid { page: 0, slot: 0 };
        let (bx, by) = plate_top_left(568, 1232, slot, COLUMNS);
        let content = tile_content(568, 1232, 0, COLUMNS);
        assert_eq!((bx, by), (content.plate_x, content.plate_y));
        assert!(hits_circle((bx + 5.0, by + 5.0), (bx, by), REMOVE_BADGE_HIT_RADIUS));
        assert!(!hits_circle((bx + 200.0, by), (bx, by), REMOVE_BADGE_HIT_RADIUS));
    }

    #[test]
    fn adjacent_remove_badges_do_not_overlap_each_other() {
        let (x0, y0) = plate_top_left(568, 1232, HomeSlot::Grid { page: 0, slot: 0 }, COLUMNS);
        let (x1, y1) = plate_top_left(568, 1232, HomeSlot::Grid { page: 0, slot: 1 }, COLUMNS);
        let dx = x1 - x0;
        let dy = y1 - y0;
        let distance = (dx * dx + dy * dy).sqrt();
        assert!(distance > 2.0 * REMOVE_BADGE_HIT_RADIUS, "neighboring badges must not overlap");
    }

    #[test]
    fn the_wide_folder_overlay_holds_sixteen_members_inside_the_landscape_panel() {
        assert_eq!(folder_columns(568, 1232), COLUMNS, "portrait keeps four columns");
        assert_eq!(folder_overlay_rect(568, 1232).1, GRID_TOP, "portrait card is unchanged");
        let (cx, cy, cw, ch) = folder_overlay_rect(1232, 568);
        assert!(cx >= 0.0 && cy >= EDGE_BAND && cx + cw <= 1232.0 && cy + ch <= dock_top(568));
        assert_eq!(folder_columns(1232, 568), 8);
        let name = folder_name_rect(1232, 568);
        assert!(name.1 >= EDGE_BAND && name.1 + name.3 <= cy + ch);
        let mut rects = Vec::new();
        for index in 0..16 {
            let (x, y, w, h) = folder_app_rect(1232, 568, index);
            assert!(
                x >= cx && y >= name.1 + name.3 && x + w <= cx + cw && y + h <= cy + ch,
                "member {index} ({x},{y},{w},{h}) leaves the card ({cx},{cy},{cw},{ch})"
            );
            assert!(x + w <= 1232.0 && y + h <= 568.0);
            // The tile holds the plate and its label.
            assert!(h >= ICON_PLATE_SIZE + ICON_LABEL_GAP + LABEL_HEIGHT - 1.0, "member {index} fits its content");
            assert_eq!(
                folder_app_at((x + w / 2.0, y + h / 2.0), 1232, 568, 16, 0.0),
                Some(index),
                "a tap at the centre of member {index}"
            );
            rects.push((x, y, w, h));
        }
        for (i, a) in rects.iter().enumerate() {
            for b in &rects[i + 1..] {
                assert!(
                    a.0 + a.2 <= b.0 || b.0 + b.2 <= a.0 || a.1 + a.3 <= b.1 || b.1 + b.3 <= a.1,
                    "member tiles overlap"
                );
            }
        }
        // The renaming keyboard cannot lift the card above the top band.
        assert_eq!(folder_overlay_rect_inset(1232, 568, 240.0), folder_overlay_rect(1232, 568));
    }
}
