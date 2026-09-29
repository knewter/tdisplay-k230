//! Home screen layout persistence and fresh-install defaults.
//!
//! Follows the exact fallback shape `theme_thumbnails.rs::disk_cache_dir_from`
//! already established for this client's other on-disk state, one directory
//! family over: state (must not be silently dropped), not cache.
//!
//! Schema 2 (this change, `the-home-screen-has-widgets-and-folders`) widens
//! each grid/dock cell from a bare desktop-entry id string to a [`HomeItem`]:
//! an app, a folder of apps, or a themed widget. Schema 1 files (bare
//! `Option<String>` cells, one app per slot) are migrated on load, not
//! rewritten in place until the next save -- see [`load`].
use crate::catalog::AppEntry;
use crate::home_grid::{self, HomeSlot};
use serde::{Deserialize, Serialize};
use std::{
    collections::HashSet,
    io::Write,
    path::{Path, PathBuf},
};

/// Current on-disk schema version. Bump and add a migration if the shape of
/// [`HomeLayout`] ever changes incompatibly.
pub const SCHEMA: u32 = 2;

/// A themed, shell-drawn widget kind. Each has a fixed cell span (see
/// [`Self::span`]) -- resizing is deliberately not supported (task: "skip it
/// if it's costly"). Four of these are clock *styles* (`home-widget-design`,
/// round 2, after `docs/design/clock-widget-research.md`: "Offer 3-4
/// genuinely striking styles") rather than four separate widget *concepts*
/// -- modeling each style as its own `WidgetKind` variant, additive to the
/// existing schema-2 tag, needs no migration at all: an old save file
/// simply never contains a new tag string, and a new save just starts using
/// it. This also means the enum variant names below are *not* renamed to
/// match round 2's own style names (Bubble/Thin/Dot matrix/Analog) --
/// renaming an already-serialized tag would break a layout a board has
/// already saved with the old names; only [`Self::label`]'s
/// user-facing string changed.
#[derive(Serialize, Deserialize, Clone, Copy, Debug, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum WidgetKind {
    /// "Bubble": hour and minute each on their own huge, heavy line, same
    /// weight and color, centered -- the fresh-install default (unchanged
    /// tag from before this change, for save-file compatibility).
    Clock,
    /// "Thin": one line, `HH:MM`, a real thin display weight, centered.
    ClockMinimal,
    /// "Analog": a drawn clock face (ticks, hour/minute hand in the theme
    /// accent, no dial background) plus a short date caption, at the same
    /// square footprint as Battery/Weather.
    ClockAnalog,
    /// "Dot matrix": a Nothing-OS-style procedural dot-matrix `HH:MM`
    /// readout, no font file involved at all.
    ClockDotMatrix,
    Battery,
    Weather,
}

impl WidgetKind {
    /// `(columns, rows)` this widget occupies, top-left anchored. The
    /// full-width clock styles (including Dot matrix, which reads better as
    /// a wide readout) are a 4x2 band; the analog face and Battery/Weather
    /// are half-width squares (2x2) -- the "obvious firsts" the task names,
    /// each at one of its listed acceptable spans.
    pub fn span(self) -> (usize, usize) {
        match self {
            WidgetKind::Clock | WidgetKind::ClockMinimal | WidgetKind::ClockDotMatrix => (4, 2),
            WidgetKind::ClockAnalog | WidgetKind::Battery | WidgetKind::Weather => (2, 2),
        }
    }

    pub const ALL: [WidgetKind; 6] = [
        WidgetKind::Clock,
        WidgetKind::ClockMinimal,
        WidgetKind::ClockAnalog,
        WidgetKind::ClockDotMatrix,
        WidgetKind::Battery,
        WidgetKind::Weather,
    ];

    pub fn label(self) -> &'static str {
        match self {
            WidgetKind::Clock => "Clock - Bubble",
            WidgetKind::ClockMinimal => "Clock - Thin",
            WidgetKind::ClockAnalog => "Clock - Analog",
            WidgetKind::ClockDotMatrix => "Clock - Dot Matrix",
            WidgetKind::Battery => "Battery",
            WidgetKind::Weather => "Weather",
        }
    }

    /// The widget-picker sheet's own one-line description of this entry,
    /// factored here (not hand-duplicated in `render.rs`) so the picker's
    /// row list and this enum's own variants can never drift out of step.
    pub fn picker_subtitle(self) -> &'static str {
        match self {
            WidgetKind::Clock => "4x2, heavy stacked hour/minute - hold to drag onto Home",
            WidgetKind::ClockMinimal => "4x2, one thin line - hold to drag onto Home",
            WidgetKind::ClockAnalog => "2x2, drawn clock face - hold to drag onto Home",
            WidgetKind::ClockDotMatrix => "4x2, procedural dot-matrix readout - hold to drag onto Home",
            WidgetKind::Battery => "2x2 - hold to drag onto Home",
            WidgetKind::Weather => "2x2 - hold to drag onto Home",
        }
    }
}

/// One folder's contents: an editable display name and its member apps in
/// display order. A folder always holds at least one app once created --
/// [`HomeLayout::remove_app`] dissolves it back into a plain [`HomeItem::App`]
/// the moment removal would leave it with exactly one, and never leaves a
/// zero-app folder on the grid at all (removal of the last app removes the
/// folder's own cell instead).
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Eq, Default)]
pub struct FolderData {
    pub name: String,
    pub apps: Vec<String>,
}

/// What occupies one grid or dock cell: an installed app (by desktop-entry
/// id, matching schema 1's own identity choice), a folder of apps, or a
/// shell-drawn widget. Only [`Self::App`] and [`Self::Folder`] are valid in
/// the dock -- a widget's span is wider than one dock cell and the dock
/// never scrolls, so [`HomeLayout::place_in_dock`] rejects a widget there.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum HomeItem {
    App { id: String },
    Folder(FolderData),
    Widget { widget: WidgetKind },
}

impl HomeItem {
    pub fn app(id: impl Into<String>) -> Self {
        HomeItem::App { id: id.into() }
    }

    /// `(columns, rows)` this item's cell covers -- 1x1 for an app or a
    /// folder tile, [`WidgetKind::span`] for a widget.
    pub fn span(&self) -> (usize, usize) {
        match self {
            HomeItem::App { .. } | HomeItem::Folder(_) => (1, 1),
            HomeItem::Widget { widget } => widget.span(),
        }
    }

    pub fn as_app_id(&self) -> Option<&str> {
        match self {
            HomeItem::App { id } => Some(id),
            _ => None,
        }
    }

    pub fn as_folder(&self) -> Option<&FolderData> {
        match self {
            HomeItem::Folder(folder) => Some(folder),
            _ => None,
        }
    }

    /// Every desktop-entry id this item is responsible for, so
    /// [`HomeLayout::contains_app`]/uninstall-hiding logic can look inside a
    /// folder without a separate code path: one id for a plain app, every
    /// member id for a folder, none for a widget.
    fn app_ids(&self) -> Vec<&str> {
        match self {
            HomeItem::App { id } => vec![id.as_str()],
            HomeItem::Folder(folder) => folder.apps.iter().map(String::as_str).collect(),
            HomeItem::Widget { .. } => Vec::new(),
        }
    }
}

/// Row-major slot indices `span` covers when its top-left corner is
/// `top_left`, at `columns` per row. A widget's covered cells beyond its own
/// top-left store `None` (see [`HomeLayout`]'s field docs) but are not free:
/// this is what [`occupied`] walks to know that.
fn covered_slots(top_left: usize, span: (usize, usize), columns: usize) -> Vec<usize> {
    let (cols, rows) = span;
    let start_col = top_left % columns;
    let start_row = top_left / columns;
    let mut out = Vec::with_capacity(cols.max(1) * rows.max(1));
    for r in 0..rows.max(1) {
        for c in 0..cols.max(1) {
            if start_col + c >= columns {
                continue; // spills past the row's right edge; `fits` rejects this placement
            }
            out.push((start_row + r) * columns + start_col + c);
        }
    }
    out
}

/// Every cell `row` already covers, whether or not that cell itself holds
/// `Some(..)` -- a multi-cell item's non-anchor cells are blocked too.
fn occupied(row: &[Option<HomeItem>], columns: usize) -> HashSet<usize> {
    let mut out = HashSet::new();
    for (index, cell) in row.iter().enumerate() {
        if let Some(item) = cell {
            out.extend(covered_slots(index, item.span(), columns));
        }
    }
    out
}

/// Whether `span` fits at `top_left` on `row`: in bounds, does not spill
/// past the row's right edge or its own last row, and does not overlap
/// anything already there. `ignore_anchor`, if given, excludes that anchor
/// cell's own footprint from the occupied set first -- used when
/// re-placing an item that already occupies part of the target (a rearrange
/// drop back onto slots it already partly covers must not see itself as a
/// collision).
fn fits(
    row: &[Option<HomeItem>],
    columns: usize,
    top_left: usize,
    span: (usize, usize),
    ignore_anchor: Option<usize>,
) -> bool {
    let (cols, _rows) = span;
    let start_col = top_left % columns;
    if start_col + cols.max(1) > columns {
        return false;
    }
    let mut blocked = occupied(row, columns);
    if let Some(anchor) = ignore_anchor {
        if let Some(item) = row.get(anchor).and_then(Option::as_ref) {
            for slot in covered_slots(anchor, item.span(), columns) {
                blocked.remove(&slot);
            }
        }
    }
    let slots = covered_slots(top_left, span, columns);
    !slots.is_empty() && slots.iter().all(|slot| *slot < row.len() && !blocked.contains(slot))
}

fn default_columns() -> usize {
    home_grid::COLUMNS
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct HomeLayout {
    pub schema: u32,
    /// Pages of grid cells, row-major within each page. `None` is either a
    /// genuinely empty cell, or a cell covered by an earlier multi-span
    /// widget's own footprint (see [`occupied`]) -- callers that need to
    /// tell those apart use [`HomeLayout::anchor_at`], never a raw index
    /// into this Vec directly.
    pub pages: Vec<Vec<Option<HomeItem>>>,
    /// Fixed dock slots, independent of the current page. Every entry here
    /// is 1x1 (`HomeItem::App` or `HomeItem::Folder`); see this module's
    /// `HomeItem` doc for why widgets are dock-ineligible.
    pub dock: Vec<Option<HomeItem>>,
    /// The grid column count every `pages` entry is currently laid out
    /// against -- every internal placement/fit/anchor computation reads
    /// this instead of `home_grid::COLUMNS` directly, so a live reflow
    /// (`reflow_to`, `feat/shell-responsive`) is the *only* thing that ever
    /// changes what a stored slot index means. `#[serde(default)]` so a
    /// schema-2 file saved before this field existed loads as `4` (this
    /// field's own pre-existing, only-ever value until now), not a parse
    /// failure.
    #[serde(default = "default_columns")]
    pub columns: usize,
}

impl Default for HomeLayout {
    fn default() -> Self {
        Self {
            schema: SCHEMA,
            pages: Vec::new(),
            dock: Vec::new(),
            columns: home_grid::COLUMNS,
        }
    }
}

impl HomeLayout {
    fn empty(dock_slots: usize) -> Self {
        Self {
            schema: SCHEMA,
            pages: vec![Vec::new()],
            dock: vec![None; dock_slots],
            columns: home_grid::COLUMNS,
        }
    }

    /// Re-lays out every page against a new column count, preserving every
    /// item's reading-order sequence (top-left to bottom-right, across
    /// pages) exactly -- never dropping, duplicating, or reordering a
    /// stored item, whether `columns` is larger (an HDMI monitor: more
    /// capacity, so nothing should need to move to a later page) or smaller
    /// (back to the panel: some items may spill onto a later page, exactly
    /// like an ordinary over-full page already does via `place_first_fit`).
    /// A no-op when `columns` already matches `self.columns` -- cheap to
    /// call defensively on every frame (`HomeScreen::sync_columns` does).
    ///
    /// Each stored item is extracted once, in row-major reading order
    /// (skipping cells a multi-span widget merely covers, via the same
    /// `covered_slots` its own placement used), then re-inserted through
    /// `place_first_fit`'s own already-tested bin-packing at the new column
    /// count -- so a multi-span widget still lands on a valid, non-
    /// overlapping rectangular footprint rather than a naive re-chunk that
    /// could split its span across two different-width rows.
    pub fn reflow_to(&mut self, columns: usize, apps_per_page: usize) {
        let columns = columns.max(1);
        if columns == self.columns {
            return;
        }
        let old_columns = self.columns.max(1);
        let mut flattened: Vec<HomeItem> = Vec::new();
        for page in &self.pages {
            let mut covered: HashSet<usize> = HashSet::new();
            for (index, cell) in page.iter().enumerate() {
                if covered.contains(&index) {
                    continue;
                }
                if let Some(item) = cell {
                    covered.extend(covered_slots(index, item.span(), old_columns));
                    flattened.push(item.clone());
                }
            }
        }
        self.pages = vec![Vec::new()];
        self.columns = columns;
        for item in flattened {
            self.place_first_fit(item, apps_per_page);
        }
    }

    /// Number of pages, always at least 1 so a fresh/empty Home still has a
    /// page to show.
    pub fn page_count(&self) -> usize {
        self.pages.len().max(1)
    }

    /// Also `pub(crate)` for `home_screen::HomeScreen::place_on_page_or_
    /// restore`'s own same-page-fallback: it must call this *before*
    /// `Self::first_fit`, because `Self::remove_slot` (already called on the
    /// drag's origin cell by the time this fallback runs) unconditionally
    /// prunes a trailing page that is still empty -- including the very
    /// (still-empty, e.g. freshly edge-hold-created) target page a
    /// cross-page drag is about to land on -- and `first_fit` itself, unlike
    /// `Self::place`, does not grow/recreate a missing page on its own.
    pub(crate) fn ensure_page(&mut self, page: usize, apps_per_page: usize) {
        while self.pages.len() <= page {
            self.pages.push(vec![None; apps_per_page.max(1)]);
        }
        let row = &mut self.pages[page];
        if row.len() < apps_per_page {
            row.resize(apps_per_page.max(1), None);
        }
    }

    /// Drops every trailing page that holds nothing at all (task: "Empty
    /// pages disappear automatically"), but never the first page -- Home
    /// always has at least one page to show, even an empty one. A page
    /// isn't just dropped anywhere it's empty: only from the end, so a
    /// later page's own index (and anything that already refers to it,
    /// e.g. an open folder or a live drag) never silently shifts.
    fn prune_trailing_empty_pages(&mut self) {
        while self.pages.len() > 1 && self.pages.last().is_some_and(|row| row.iter().all(Option::is_none)) {
            self.pages.pop();
        }
    }

    /// The item occupying `slot`'s own cell, if `slot` is itself an item's
    /// anchor (top-left) cell. `None` both for a genuinely empty cell and
    /// for a cell merely covered by a neighboring multi-span widget --
    /// distinguishing those two isn't needed by any caller today, but see
    /// [`Self::anchor_at`] for the one that is.
    pub fn get(&self, slot: HomeSlot) -> Option<&HomeItem> {
        match slot {
            HomeSlot::Grid { page, slot } => self.pages.get(page).and_then(|row| row.get(slot)).and_then(Option::as_ref),
            HomeSlot::Dock { slot } => self.dock.get(slot).and_then(Option::as_ref),
        }
    }

    /// The slot and item actually responsible for `slot` -- `slot` itself if
    /// it is an item's own anchor, or the anchor of whichever multi-span
    /// widget's footprint covers it otherwise. Used by hit-testing so a tap
    /// or drag anywhere within a Clock/Battery/Weather tile's whole span
    /// resolves to that widget, not nothing.
    pub fn anchor_at(&self, slot: HomeSlot) -> Option<(HomeSlot, &HomeItem)> {
        if let Some(item) = self.get(slot) {
            return Some((slot, item));
        }
        if let HomeSlot::Grid { page, slot: index } = slot {
            let row = self.pages.get(page)?;
            let columns = self.columns.max(1);
            for (anchor, cell) in row.iter().enumerate() {
                if let Some(item) = cell {
                    if covered_slots(anchor, item.span(), columns).contains(&index) {
                        return Some((HomeSlot::Grid { page, slot: anchor }, item));
                    }
                }
            }
        }
        None
    }

    /// Writes `item` into `slot`, growing pages/rows as needed, first
    /// clearing whatever cell(s) `slot` itself used to anchor (so replacing
    /// a wide widget with a plain app doesn't leave its old covered cells
    /// permanently blocked). Does not check fit -- callers that must not
    /// overlap another item use [`Self::place`] instead; this is the raw
    /// primitive persistence's own migration and tests use.
    pub fn set(&mut self, slot: HomeSlot, item: Option<HomeItem>, apps_per_page: usize) {
        match slot {
            HomeSlot::Grid { page, slot } => {
                self.ensure_page(page, apps_per_page);
                if let Some(cell) = self.pages[page].get_mut(slot) {
                    *cell = item;
                }
            }
            HomeSlot::Dock { slot } => {
                if let Some(cell) = self.dock.get_mut(slot) {
                    *cell = item;
                }
            }
        }
        self.prune_trailing_empty_pages();
    }

    /// Whether `item` fits at `slot` without overlapping another item's
    /// footprint (a plain out-of-range dock index, or a grid page/row that
    /// does not exist yet, also counts as not fitting -- callers grow the
    /// page with [`Self::ensure_page`]-backed [`Self::place`] instead of
    /// calling this directly against an ungrown page).
    fn fits_at(&self, slot: HomeSlot, span: (usize, usize), ignore_anchor: bool) -> bool {
        match slot {
            HomeSlot::Grid { page, slot: index } => {
                let Some(row) = self.pages.get(page) else { return false };
                let ignore = ignore_anchor.then_some(index);
                fits(row, self.columns.max(1), index, span, ignore)
            }
            HomeSlot::Dock { slot: index } => span == (1, 1) && index < self.dock.len(),
        }
    }

    /// Appends one brand-new, entirely empty page and returns its index --
    /// the cross-page drag's "dragging onto the last page's right edge
    /// creates a new page" (`home-widget-design` task 1). Distinct from the
    /// private `ensure_page` (which only grows far enough to reach an index
    /// something else is about to write into): this unconditionally adds
    /// one page, even when the current last page still has free cells,
    /// because a person dragging all the way to the last page's edge is
    /// asking for a fresh page to land on, not to be quietly redirected
    /// back onto whatever room that page still has.
    pub fn add_blank_page(&mut self, apps_per_page: usize) -> usize {
        self.pages.push(vec![None; apps_per_page.max(1)]);
        self.pages.len() - 1
    }

    /// Whether an item of `span` would fit at `slot` -- the live "no room
    /// here" drop indicator (`home-widget-design` task 1) calls this so the
    /// renderer can tell an ordinary accepting drop target from one a
    /// multi-cell widget's drag cannot actually land on, without mutating
    /// anything. A page index past the end of `pages` always answers `true`
    /// for a grid slot: dropping there grows a fresh page first (see
    /// `Self::place`/`Self::ensure_page`), so nothing is actually blocked.
    pub fn would_fit(&self, slot: HomeSlot, span: (usize, usize)) -> bool {
        match slot {
            HomeSlot::Grid { page, .. } if page >= self.pages.len() => true,
            _ => self.fits_at(slot, span, false),
        }
    }

    /// Places `item` at `slot`'s anchor if it fits there, growing the page
    /// first. Returns `false` (and leaves the layout unchanged) if it does
    /// not fit -- a widget spilling off the row's edge, or a widget aimed at
    /// the dock. `ignore_anchor` excludes `slot`'s own existing footprint
    /// from the collision check first (re-placing an item back onto cells
    /// it already partly occupies).
    pub fn place(&mut self, slot: HomeSlot, item: HomeItem, apps_per_page: usize, ignore_anchor: bool) -> bool {
        if let HomeSlot::Grid { page, .. } = slot {
            self.ensure_page(page, apps_per_page);
        }
        if !self.fits_at(slot, item.span(), ignore_anchor) {
            return false;
        }
        self.set(slot, Some(item), apps_per_page);
        true
    }

    /// The first free anchor cell on `page` that fits `item`'s span, if any
    /// -- used by [`Self::pin`]/[`Self::place_first_fit`] to fill a page
    /// left-to-right, top-to-bottom. Also `pub(crate)` for
    /// `home_screen::HomeScreen::move_existing`/`drop_dragged_item`'s own
    /// same-page fallback: a rearrange drag that resolves to no slot at all
    /// (released right in the edge margin past the last tile column) or to
    /// an occupied, non-mergeable, differently-sized target must still land
    /// somewhere on the page it's *currently over*, not silently revert to
    /// its origin (home-widget-design cross-page-drop-reverts fix).
    pub(crate) fn first_fit(&self, page: usize, item: &HomeItem, apps_per_page: usize) -> Option<usize> {
        let row = self.pages.get(page)?;
        let len = row.len().max(apps_per_page);
        (0..len).find(|&index| fits(row, self.columns.max(1), index, item.span(), None))
    }

    /// Places `item` in the first free-fitting cell across existing pages,
    /// adding a new page when every existing one is full -- the drawer's
    /// long-press-drag falls back to this for the rare release that lands
    /// nowhere resolvable (e.g. a drop point past the last page during an
    /// aborted edge-switch); ordinary placement instead goes through
    /// [`Self::place`] at the exact dropped slot.
    pub fn place_first_fit(&mut self, item: HomeItem, apps_per_page: usize) -> HomeSlot {
        let mut page = 0;
        loop {
            self.ensure_page(page, apps_per_page);
            if let Some(index) = self.first_fit(page, &item, apps_per_page) {
                self.pages[page][index] = Some(item);
                return HomeSlot::Grid { page, slot: index };
            }
            page += 1;
            if page > self.pages.len() {
                // Defensive bound: `first_fit` against a freshly-grown empty
                // page can never fail, so this only guards a pathological
                // `apps_per_page` of 0.
                self.pages.push(vec![None; 1.max(apps_per_page)]);
            }
        }
    }

    /// Pins `id` into the first free grid slot, adding a new page when
    /// every existing page is full. A no-op if `id` is already pinned
    /// anywhere -- grid, dock, or inside a folder.
    pub fn pin(&mut self, id: String, apps_per_page: usize) {
        if self.contains_app(&id) {
            return;
        }
        self.place_first_fit(HomeItem::app(id), apps_per_page);
    }

    /// Whether `id` already occupies some grid or dock slot, directly or as
    /// a folder member.
    pub fn contains_app(&self, id: &str) -> bool {
        self.pages
            .iter()
            .flatten()
            .chain(self.dock.iter())
            .flatten()
            .any(|item| item.app_ids().contains(&id))
    }

    /// Removes `id` from wherever it lives on Home: its own cell if pinned
    /// directly, or out of a folder if it is a folder member -- dissolving
    /// that folder back into a plain [`HomeItem::App`] the moment only one
    /// member would remain (task: "A folder with one app left dissolves
    /// into that app"), and clearing the cell entirely if removal would
    /// leave zero. A no-op if `id` is not pinned anywhere.
    pub fn remove_app(&mut self, id: &str) {
        for row in self.pages.iter_mut() {
            for cell in row.iter_mut() {
                Self::remove_from_cell(cell, id);
            }
        }
        for cell in self.dock.iter_mut() {
            Self::remove_from_cell(cell, id);
        }
        self.prune_trailing_empty_pages();
    }

    fn remove_from_cell(cell: &mut Option<HomeItem>, id: &str) {
        match cell {
            Some(HomeItem::App { id: cell_id }) if cell_id == id => *cell = None,
            Some(HomeItem::Folder(folder)) if folder.apps.iter().any(|app| app == id) => {
                folder.apps.retain(|app| app != id);
                match folder.apps.len() {
                    0 => *cell = None,
                    1 => *cell = Some(HomeItem::app(folder.apps[0].clone())),
                    _ => {}
                }
            }
            _ => {}
        }
    }

    /// Removes whatever item anchors `slot` entirely (an app, a whole
    /// folder including its members, or a widget) -- distinct from
    /// [`Self::remove_app`], which only ever removes one app id and may
    /// leave its folder behind with fewer members.
    pub fn remove_slot(&mut self, slot: HomeSlot) {
        self.set(slot, None, 1);
    }

    /// Builds a fresh Home layout when no saved one exists: the curated
    /// defaults fill the dock first (up to `dock_slots`), then the
    /// remaining curated defaults (if any) fill the first grid page's own
    /// first cells, and a Clock widget seeds the top of that same page --
    /// task: "clock... in theme colours" is the one widget worth a fresh
    /// install actually showing rather than an empty grid.
    pub fn seed(apps: &[AppEntry], dock_slots: usize, apps_per_page: usize) -> Self {
        let defaults = curated_defaults(apps);
        let mut layout = HomeLayout::empty(dock_slots);
        let mut iter = defaults.into_iter();
        for slot in layout.dock.iter_mut() {
            let Some(id) = iter.next() else { break };
            *slot = Some(HomeItem::app(id));
        }
        layout.ensure_page(0, apps_per_page);
        layout.place(HomeSlot::Grid { page: 0, slot: 0 }, HomeItem::Widget { widget: WidgetKind::Clock }, apps_per_page, false);
        for id in iter {
            let item = HomeItem::app(id);
            if let Some(index) = layout.first_fit(0, &item, apps_per_page) {
                layout.pages[0][index] = Some(item);
            }
        }
        layout
    }
}

/// `$XDG_STATE_HOME/k230-shell/home.json`, or
/// `$HOME/.local/state/k230-shell/home.json` when `XDG_STATE_HOME` is unset
/// or empty. `None` when neither is available (a stripped test/service
/// environment): callers simply run with an in-memory default in that case.
pub fn state_path() -> Option<PathBuf> {
    state_path_from(
        std::env::var("XDG_STATE_HOME").ok().as_deref(),
        std::env::var("HOME").ok().as_deref(),
    )
}

/// `state_path`'s actual logic, taking its two env var readings as plain
/// arguments so tests can exercise the XDG/HOME fallback without mutating
/// real process-wide environment state.
fn state_path_from(xdg_state_home: Option<&str>, home: Option<&str>) -> Option<PathBuf> {
    if let Some(dir) = xdg_state_home {
        if !dir.trim().is_empty() {
            return Some(PathBuf::from(dir).join("k230-shell/home.json"));
        }
    }
    let home = home?;
    if home.trim().is_empty() {
        return None;
    }
    Some(PathBuf::from(home).join(".local/state/k230-shell/home.json"))
}

const MAX_FILE_BYTES: u64 = 256 * 1024;

/// Schema 1's on-disk shape (bare app-id strings, one per cell): kept only
/// as a migration source for [`load`], never written again.
#[derive(Deserialize)]
struct HomeLayoutV1 {
    #[allow(dead_code)]
    schema: u32,
    pages: Vec<Vec<Option<String>>>,
    dock: Vec<Option<String>>,
}

impl From<HomeLayoutV1> for HomeLayout {
    fn from(old: HomeLayoutV1) -> Self {
        HomeLayout {
            schema: SCHEMA,
            pages: old
                .pages
                .into_iter()
                .map(|row| row.into_iter().map(|cell| cell.map(HomeItem::app)).collect())
                .collect(),
            dock: old.dock.into_iter().map(|cell| cell.map(HomeItem::app)).collect(),
            // Schema 1 predates per-column reflow entirely; its cells were
            // always laid out at the reference 4 columns.
            columns: home_grid::COLUMNS,
        }
    }
}

/// Loads a previously saved layout, migrating a schema 1 file (bare id
/// strings) to schema 2 (`HomeItem`) in memory -- the file itself is not
/// rewritten until the next [`save`], matching every other best-effort
/// on-disk state in this client. Returns `None` on a missing file, oversized
/// file, or any parse failure in *both* shapes -- callers fall back to
/// [`HomeLayout::seed`] in every one of those cases, so a corrupt file never
/// crashes the shell, it just re-seeds.
pub fn load(path: &Path) -> Option<HomeLayout> {
    let metadata = std::fs::metadata(path).ok()?;
    if !metadata.is_file() || metadata.len() > MAX_FILE_BYTES {
        return None;
    }
    let bytes = std::fs::read(path).ok()?;
    if let Ok(layout) = serde_json::from_slice::<HomeLayout>(&bytes) {
        return Some(layout);
    }
    serde_json::from_slice::<HomeLayoutV1>(&bytes).ok().map(HomeLayout::from)
}

/// Writes `layout` atomically: a sibling temp file, then a rename, so a
/// crash or power loss mid-write never leaves a half-written layout file
/// behind for the next `load` to choke on.
pub fn save(path: &Path, layout: &HomeLayout) -> Result<(), String> {
    let Some(parent) = path.parent() else {
        return Err("state path has no parent directory".into());
    };
    std::fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    let bytes = serde_json::to_vec_pretty(layout).map_err(|error| error.to_string())?;
    let temp = parent.join(format!(
        ".home.json.tmp.{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|duration| duration.as_nanos())
            .unwrap_or_default()
    ));
    {
        let mut file = std::fs::File::create(&temp).map_err(|error| error.to_string())?;
        file.write_all(&bytes).map_err(|error| error.to_string())?;
        file.sync_all().map_err(|error| error.to_string())?;
    }
    std::fs::rename(&temp, path).map_err(|error| error.to_string())
}

/// One curated default category: a human label (unused at runtime, kept for
/// readability/tests) and the lowercase substrings matched against both the
/// desktop-entry id and its display name. The first installed app matching
/// any keyword in a category is used; a category with no installed match is
/// silently omitted, never shown as a placeholder.
const DEFAULT_CATEGORIES: &[(&str, &[&str])] = &[
    ("terminal", &["term", "foot", "console"]),
    (
        "files",
        &["files", "nautilus", "filemanager", "file-manager", "pcmanfm", "thunar", "file manager"],
    ),
    (
        "editor",
        &["texteditor", "text-editor", "text editor", "gedit", "editor", "code"],
    ),
    (
        "monitor",
        &["htop", "monitor", "system-monitor", "system monitor", "taskmanager", "task manager"],
    ),
    ("video", &["video", "player", "mpv", "vlc"]),
    (
        "settings",
        &["settings", "control-center", "control center", "preferences"],
    ),
];

fn matches_category(app: &AppEntry, keywords: &[&str]) -> bool {
    let id = app.id.to_lowercase();
    let name = app.name.to_lowercase();
    keywords.iter().any(|word| id.contains(word) || name.contains(word))
}

/// Picks the curated default apps present on this image, in
/// `DEFAULT_CATEGORIES` priority order, each category contributing at most
/// one app and never a placeholder when nothing installed matches it.
pub fn curated_defaults(apps: &[AppEntry]) -> Vec<String> {
    let mut chosen = Vec::new();
    for (_label, keywords) in DEFAULT_CATEGORIES {
        if let Some(app) = apps.iter().find(|app| matches_category(app, keywords)) {
            if !chosen.contains(&app.id) {
                chosen.push(app.id.clone());
            }
        }
    }
    chosen
}

/// Builds a fresh Home layout when no saved one exists. Thin wrapper kept
/// for the existing call convention; see [`HomeLayout::seed`].
pub fn seed_default(apps: &[AppEntry], dock_slots: usize, apps_per_page: usize) -> HomeLayout {
    HomeLayout::seed(apps, dock_slots, apps_per_page)
}

/// Loads the saved layout, or seeds and immediately persists a fresh
/// default when none exists (or the saved file could not be read), so a
/// second boot is stable even before anything is intentionally pinned.
/// `path` is `None` in a stripped environment with no usable state
/// directory; the seed then simply is not persisted, exactly as if a write
/// failed, and the shell continues with an in-memory default.
pub fn load_or_seed(
    path: Option<&Path>,
    apps: &[AppEntry],
    dock_slots: usize,
    apps_per_page: usize,
) -> HomeLayout {
    if let Some(path) = path {
        if let Some(layout) = load(path) {
            return layout;
        }
    }
    let layout = seed_default(apps, dock_slots, apps_per_page);
    if let Some(path) = path {
        let _ = save(path, &layout);
    }
    layout
}

#[cfg(test)]
mod tests {
    use super::*;

    fn app(id: &str, name: &str) -> AppEntry {
        AppEntry {
            id: id.into(),
            name: name.into(),
            icon: None,
            path: PathBuf::new(),
        }
    }

    /// Every app anchor in `layout`'s pages, in reading order (page, then
    /// row-major within it, skipping cells a multi-span item merely
    /// covers) -- the same order `HomeLayout::reflow_to` itself flattens
    /// in, used here to assert that order survives a reflow untouched.
    fn flattened_order(layout: &HomeLayout) -> Vec<HomeItem> {
        let mut out = Vec::new();
        for page in &layout.pages {
            let mut covered: HashSet<usize> = HashSet::new();
            for (index, cell) in page.iter().enumerate() {
                if covered.contains(&index) {
                    continue;
                }
                if let Some(item) = cell {
                    covered.extend(covered_slots(index, item.span(), layout.columns.max(1)));
                    out.push(item.clone());
                }
            }
        }
        out
    }

    #[test]
    fn reflow_to_a_wider_column_count_never_loses_or_reorders_items() {
        let mut layout = HomeLayout { dock: vec![None; 4], ..HomeLayout::default() };
        assert_eq!(layout.columns, home_grid::COLUMNS);
        let names = ["a", "b", "c", "d", "e", "f", "g", "h", "i"];
        for name in names {
            layout.place_first_fit(HomeItem::app(format!("{name}.desktop")), 20);
        }
        let before = flattened_order(&layout);
        assert_eq!(before.len(), names.len(), "every placed item is present before reflow");

        layout.reflow_to(8, 40);
        assert_eq!(layout.columns, 8);
        let after = flattened_order(&layout);
        assert_eq!(after, before, "reading-order sequence is byte-for-byte unchanged by growing columns");
        // A wider grid has strictly more per-page capacity, so nothing that
        // fit on one page before should have spilled onto a second page.
        assert_eq!(layout.pages.len(), 1);
    }

    #[test]
    fn reflow_to_round_trips_4_then_8_then_back_to_4() {
        let mut layout = HomeLayout { dock: vec![None; 4], ..HomeLayout::default() };
        for name in ["a", "b", "c", "d", "e", "f"] {
            layout.place_first_fit(HomeItem::app(format!("{name}.desktop")), 20);
        }
        let original = layout.clone();
        let original_order = flattened_order(&original);

        layout.reflow_to(8, 40);
        assert_ne!(layout.pages, original.pages, "column count actually changed the stored shape");
        layout.reflow_to(4, 20);

        assert_eq!(layout.columns, 4);
        assert_eq!(
            flattened_order(&layout),
            original_order,
            "round-tripping 4 -> 8 -> 4 preserves the exact original reading order"
        );
        // With every item comfortably fitting on one page at 4 columns both
        // before and after, the round trip reproduces the identical page
        // shape, not just the same order -- a stronger check than order
        // alone, since a naive reflow could preserve order while still
        // scattering items across extra empty pages.
        assert_eq!(layout.pages, original.pages);
    }

    #[test]
    fn reflow_to_is_a_no_op_when_columns_already_match() {
        let mut layout = HomeLayout { dock: vec![None; 4], ..HomeLayout::default() };
        layout.place_first_fit(HomeItem::app("a.desktop"), 20);
        let before = layout.clone();
        layout.reflow_to(home_grid::COLUMNS, 20);
        assert_eq!(layout, before, "reflowing to the already-current column count changes nothing");
    }

    #[test]
    fn reflow_to_keeps_a_multi_span_widget_intact_as_one_item() {
        let mut layout = HomeLayout { dock: vec![None; 4], ..HomeLayout::default() };
        layout.place_first_fit(HomeItem::Widget { widget: WidgetKind::Clock }, 20);
        layout.place_first_fit(HomeItem::app("a.desktop"), 20);
        layout.place_first_fit(HomeItem::app("b.desktop"), 20);
        let before = flattened_order(&layout);
        assert_eq!(before[0], HomeItem::Widget { widget: WidgetKind::Clock });

        layout.reflow_to(8, 40);
        let after = flattened_order(&layout);
        assert_eq!(after, before, "the widget stays exactly one item, in its original position");
        // Its footprint at the new column count must still be a single,
        // valid, non-overlapping rectangular span, not split across rows.
        let (page, anchor) = layout
            .pages
            .iter()
            .enumerate()
            .find_map(|(page, row)| row.iter().position(|cell| matches!(cell, Some(HomeItem::Widget { .. }))).map(|slot| (page, slot)))
            .expect("the widget is still anchored somewhere");
        assert!(fits(&layout.pages[page], layout.columns, anchor, (4, 2), Some(anchor)));
    }

    #[test]
    fn state_path_prefers_xdg_then_home_then_none() {
        assert_eq!(
            state_path_from(Some("/xdg"), Some("/home/user")),
            Some(PathBuf::from("/xdg/k230-shell/home.json"))
        );
        assert_eq!(
            state_path_from(Some(""), Some("/home/user")),
            Some(PathBuf::from("/home/user/.local/state/k230-shell/home.json"))
        );
        assert_eq!(state_path_from(None, Some("")), None);
        assert_eq!(state_path_from(None, None), None);
    }

    #[test]
    fn curated_defaults_skip_missing_categories_and_dedupe() {
        let apps = vec![
            app("foot.desktop", "Foot"),
            app("org.gnome.TextEditor.desktop", "Text Editor"),
            app("htop.desktop", "Htop"),
        ];
        let defaults = curated_defaults(&apps);
        assert_eq!(
            defaults,
            vec!["foot.desktop", "org.gnome.TextEditor.desktop", "htop.desktop"],
            "priority order, files/video/settings omitted (not installed)"
        );
    }

    #[test]
    fn seed_default_fills_dock_before_grid_and_seeds_a_clock() {
        let apps = vec![
            app("foot.desktop", "Foot"),
            app("files.desktop", "Files"),
            app("editor.desktop", "Text Editor"),
            app("htop.desktop", "System Monitor"),
            app("video.desktop", "Video Player"),
            app("settings.desktop", "Settings"),
        ];
        let layout = seed_default(&apps, 4, 8);
        assert_eq!(
            layout.dock,
            vec![
                Some(HomeItem::app("foot.desktop")),
                Some(HomeItem::app("files.desktop")),
                Some(HomeItem::app("editor.desktop")),
                Some(HomeItem::app("htop.desktop")),
            ]
        );
        assert_eq!(layout.pages.len(), 1);
        assert_eq!(
            layout.pages[0][0],
            Some(HomeItem::Widget { widget: WidgetKind::Clock })
        );
        // The clock is 4x2 on an 8-cell (4-wide, 2-row) page, so it alone
        // fills the whole page; the remaining curated apps overflow to a
        // new page.
        assert!(layout.pages[0][1..].iter().all(Option::is_none));
    }

    #[test]
    fn seed_default_with_nothing_installed_is_still_a_clock_only_home() {
        let layout = seed_default(&[], 4, 8);
        assert_eq!(layout.dock, vec![None, None, None, None]);
        assert_eq!(layout.pages.len(), 1);
        assert_eq!(
            layout.pages[0][0],
            Some(HomeItem::Widget { widget: WidgetKind::Clock })
        );
    }

    #[test]
    fn save_then_load_round_trips_exactly() {
        let dir = std::env::temp_dir().join(format!(
            "k230-home-state-{}-{}",
            std::process::id(),
            std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()
        ));
        let path = dir.join("home.json");
        let layout = HomeLayout {
            schema: SCHEMA,
            pages: vec![vec![Some(HomeItem::app("a.desktop")), None, Some(HomeItem::app("b.desktop"))]],
            dock: vec![Some(HomeItem::app("c.desktop")), None],
            columns: home_grid::COLUMNS,
        };
        save(&path, &layout).unwrap();
        assert_eq!(load(&path), Some(layout));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn a_schema_1_file_migrates_to_plain_apps_on_load() {
        let dir = std::env::temp_dir().join(format!(
            "k230-home-state-v1-{}-{}",
            std::process::id(),
            std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("home.json");
        let v1_json = serde_json::json!({
            "schema": 1,
            "pages": [[ "a.desktop", null, "b.desktop" ]],
            "dock": [ "c.desktop", null ],
        });
        std::fs::write(&path, serde_json::to_vec(&v1_json).unwrap()).unwrap();
        let migrated = load(&path).expect("v1 file migrates");
        assert_eq!(migrated.schema, SCHEMA);
        assert_eq!(migrated.pages[0][0], Some(HomeItem::app("a.desktop")));
        assert_eq!(migrated.pages[0][1], None);
        assert_eq!(migrated.pages[0][2], Some(HomeItem::app("b.desktop")));
        assert_eq!(migrated.dock[0], Some(HomeItem::app("c.desktop")));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn load_or_seed_persists_the_seed_so_a_second_boot_is_stable() {
        let dir = std::env::temp_dir().join(format!(
            "k230-home-state-seed-{}-{}",
            std::process::id(),
            std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()
        ));
        let path = dir.join("home.json");
        let apps = vec![app("foot.desktop", "Foot")];
        let first = load_or_seed(Some(&path), &apps, 4, 8);
        assert_eq!(first.dock[0], Some(HomeItem::app("foot.desktop")));
        let changed_apps = vec![app("other.desktop", "Other")];
        let second = load_or_seed(Some(&path), &changed_apps, 4, 8);
        assert_eq!(second, first);
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn missing_entry_keeps_its_slot_on_load() {
        let dir = std::env::temp_dir().join(format!(
            "k230-home-state-missing-{}-{}",
            std::process::id(),
            std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()
        ));
        let path = dir.join("home.json");
        let layout = HomeLayout {
            schema: SCHEMA,
            pages: vec![vec![Some(HomeItem::app("gone.desktop")), None]],
            dock: vec![None; 4],
            columns: home_grid::COLUMNS,
        };
        save(&path, &layout).unwrap();
        let loaded = load(&path).unwrap();
        assert_eq!(loaded.pages[0][0], Some(HomeItem::app("gone.desktop")));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn corrupt_file_falls_back_to_seed_rather_than_crashing() {
        let dir = std::env::temp_dir().join(format!(
            "k230-home-state-corrupt-{}-{}",
            std::process::id(),
            std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("home.json");
        std::fs::write(&path, b"not json").unwrap();
        assert_eq!(load(&path), None);
        let apps = vec![app("foot.desktop", "Foot")];
        let layout = load_or_seed(Some(&path), &apps, 4, 8);
        assert_eq!(layout.dock[0], Some(HomeItem::app("foot.desktop")));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn pin_fills_first_free_slot_then_adds_a_page_when_full() {
        let mut layout = HomeLayout::empty(4);
        layout.place(HomeSlot::Grid { page: 0, slot: 0 }, HomeItem::app("a.desktop"), 2, false);
        layout.pin("b.desktop".into(), 2);
        assert_eq!(layout.get(HomeSlot::Grid { page: 0, slot: 1 }), Some(&HomeItem::app("b.desktop")));
        layout.pin("c.desktop".into(), 2);
        assert_eq!(layout.page_count(), 2);
        assert_eq!(layout.get(HomeSlot::Grid { page: 1, slot: 0 }), Some(&HomeItem::app("c.desktop")));
    }

    #[test]
    fn pin_is_a_no_op_for_an_already_pinned_app() {
        let mut layout = HomeLayout::empty(4);
        layout.place(HomeSlot::Grid { page: 0, slot: 2 }, HomeItem::app("a.desktop"), 4, false);
        layout.pin("a.desktop".into(), 4);
        assert_eq!(layout.get(HomeSlot::Grid { page: 0, slot: 2 }), Some(&HomeItem::app("a.desktop")));
        assert_eq!(layout.get(HomeSlot::Grid { page: 0, slot: 0 }), None, "did not duplicate elsewhere");
        let mut layout = HomeLayout::empty(4);
        layout.place(HomeSlot::Dock { slot: 1 }, HomeItem::app("b.desktop"), 4, false);
        layout.pin("b.desktop".into(), 4);
        assert_eq!(layout.get(HomeSlot::Dock { slot: 1 }), Some(&HomeItem::app("b.desktop")));
    }

    #[test]
    fn pin_is_a_no_op_for_an_app_already_inside_a_folder() {
        let mut layout = HomeLayout::empty(4);
        layout.place(
            HomeSlot::Grid { page: 0, slot: 0 },
            HomeItem::Folder(FolderData { name: "Fun".into(), apps: vec!["a.desktop".into(), "b.desktop".into()] }),
            4,
            false,
        );
        layout.pin("a.desktop".into(), 4);
        assert_eq!(layout.get(HomeSlot::Grid { page: 0, slot: 1 }), None, "not duplicated outside the folder");
    }

    #[test]
    fn remove_app_clears_a_plain_cell_without_shifting_neighbors() {
        let mut layout = HomeLayout::empty(4);
        layout.place(HomeSlot::Grid { page: 0, slot: 0 }, HomeItem::app("a.desktop"), 4, false);
        layout.place(HomeSlot::Grid { page: 0, slot: 1 }, HomeItem::app("b.desktop"), 4, false);
        layout.remove_app("a.desktop");
        assert_eq!(layout.get(HomeSlot::Grid { page: 0, slot: 0 }), None);
        assert_eq!(layout.get(HomeSlot::Grid { page: 0, slot: 1 }), Some(&HomeItem::app("b.desktop")));
    }

    #[test]
    fn remove_app_dissolves_a_two_app_folder_into_the_remaining_app() {
        let mut layout = HomeLayout::empty(4);
        layout.place(
            HomeSlot::Grid { page: 0, slot: 0 },
            HomeItem::Folder(FolderData { name: "Fun".into(), apps: vec!["a.desktop".into(), "b.desktop".into()] }),
            4,
            false,
        );
        layout.remove_app("a.desktop");
        assert_eq!(layout.get(HomeSlot::Grid { page: 0, slot: 0 }), Some(&HomeItem::app("b.desktop")));
    }

    #[test]
    fn remove_app_from_a_three_app_folder_keeps_it_a_folder() {
        let mut layout = HomeLayout::empty(4);
        layout.place(
            HomeSlot::Grid { page: 0, slot: 0 },
            HomeItem::Folder(FolderData {
                name: "Fun".into(),
                apps: vec!["a.desktop".into(), "b.desktop".into(), "c.desktop".into()],
            }),
            4,
            false,
        );
        layout.remove_app("a.desktop");
        let folder = layout.get(HomeSlot::Grid { page: 0, slot: 0 }).unwrap().as_folder().unwrap();
        assert_eq!(folder.apps, vec!["b.desktop", "c.desktop"]);
    }

    #[test]
    fn remove_slot_deletes_a_whole_folder_including_its_members() {
        let mut layout = HomeLayout::empty(4);
        layout.place(
            HomeSlot::Grid { page: 0, slot: 0 },
            HomeItem::Folder(FolderData { name: "Fun".into(), apps: vec!["a.desktop".into(), "b.desktop".into()] }),
            4,
            false,
        );
        layout.remove_slot(HomeSlot::Grid { page: 0, slot: 0 });
        assert_eq!(layout.get(HomeSlot::Grid { page: 0, slot: 0 }), None);
        assert!(!layout.contains_app("a.desktop"));
    }

    #[test]
    fn a_widget_blocks_every_cell_of_its_span_from_a_second_placement() {
        let mut layout = HomeLayout::empty(4);
        assert!(layout.place(HomeSlot::Grid { page: 0, slot: 0 }, HomeItem::Widget { widget: WidgetKind::Clock }, 8, false));
        // Clock is 4x2 on a 4-column grid: slots 0..8 are all covered.
        for slot in 0..8 {
            assert!(
                !layout.fits_at(HomeSlot::Grid { page: 0, slot }, (1, 1), false),
                "slot {slot} should be blocked by the clock's own span"
            );
        }
        assert!(layout.place(HomeSlot::Grid { page: 0, slot: 8 }, HomeItem::app("a.desktop"), 12, false));
    }

    #[test]
    fn a_widget_spilling_past_the_row_edge_does_not_fit() {
        let mut layout = HomeLayout::empty(4);
        // Battery is 2x2; anchoring it at column 3 (the last of 4 columns)
        // would spill one column past the row's right edge.
        assert!(!layout.place(HomeSlot::Grid { page: 0, slot: 3 }, HomeItem::Widget { widget: WidgetKind::Battery }, 8, false));
    }

    #[test]
    fn anchor_at_resolves_any_covered_cell_to_the_widgets_own_anchor() {
        let mut layout = HomeLayout::empty(4);
        layout.place(HomeSlot::Grid { page: 0, slot: 0 }, HomeItem::Widget { widget: WidgetKind::Clock }, 8, false);
        for slot in 0..8 {
            let (anchor, item) = layout.anchor_at(HomeSlot::Grid { page: 0, slot }).expect("covered by the clock");
            assert_eq!(anchor, HomeSlot::Grid { page: 0, slot: 0 });
            assert_eq!(item, &HomeItem::Widget { widget: WidgetKind::Clock });
        }
        assert!(layout.anchor_at(HomeSlot::Grid { page: 0, slot: 8 }).is_none());
    }

    #[test]
    fn widgets_are_not_dock_eligible() {
        let mut layout = HomeLayout::empty(4);
        assert!(!layout.place(HomeSlot::Dock { slot: 0 }, HomeItem::Widget { widget: WidgetKind::Battery }, 4, false));
        assert_eq!(layout.get(HomeSlot::Dock { slot: 0 }), None);
    }

    #[test]
    fn the_four_clock_styles_have_their_documented_spans_and_are_all_pickable() {
        assert_eq!(WidgetKind::Clock.span(), (4, 2));
        assert_eq!(WidgetKind::ClockMinimal.span(), (4, 2));
        assert_eq!(WidgetKind::ClockAnalog.span(), (2, 2));
        assert_eq!(WidgetKind::ClockDotMatrix.span(), (4, 2));
        assert_eq!(WidgetKind::ALL.len(), 6);
        assert!(WidgetKind::ALL.contains(&WidgetKind::ClockMinimal));
        assert!(WidgetKind::ALL.contains(&WidgetKind::ClockAnalog));
        assert!(WidgetKind::ALL.contains(&WidgetKind::ClockDotMatrix));
        // Every entry has a distinct label -- the picker list would silently
        // conflate two rows otherwise.
        let mut labels: Vec<&str> = WidgetKind::ALL.iter().map(|kind| kind.label()).collect();
        labels.sort_unstable();
        labels.dedup();
        assert_eq!(labels.len(), WidgetKind::ALL.len());
    }

    #[test]
    fn add_blank_page_always_appends_even_when_the_last_page_has_room() {
        let mut layout = HomeLayout::empty(4);
        layout.place(HomeSlot::Grid { page: 0, slot: 0 }, HomeItem::app("a.desktop"), 8, false);
        assert_eq!(layout.page_count(), 1);
        let new_index = layout.add_blank_page(8);
        assert_eq!(new_index, 1);
        assert_eq!(layout.page_count(), 2);
        assert!(layout.pages[1].iter().all(Option::is_none));
        // A second call always adds a third page too, even though page 1 is
        // itself still empty -- dragging to the true last page's edge keeps
        // producing a fresh page, not silently reusing the one just made.
        let third = layout.add_blank_page(8);
        assert_eq!(third, 2);
        assert_eq!(layout.page_count(), 3);
    }

    #[test]
    fn would_fit_matches_fits_at_for_an_existing_page_and_always_allows_a_future_one() {
        let mut layout = HomeLayout::empty(4);
        // 16 = 4 rows of 4 columns: the clock's own 4x2 span covers slots
        // 0..8 (rows 0-1), leaving rows 2-3 (slots 8..16) free -- a 2x2 at
        // slot 8 needs all of rows 2 and 3 to exist.
        layout.place(HomeSlot::Grid { page: 0, slot: 0 }, HomeItem::Widget { widget: WidgetKind::Clock }, 16, false);
        assert!(!layout.would_fit(HomeSlot::Grid { page: 0, slot: 0 }, (2, 2)), "already covered by the clock");
        assert!(layout.would_fit(HomeSlot::Grid { page: 0, slot: 8 }, (2, 2)), "free cell on the existing page");
        assert!(
            layout.would_fit(HomeSlot::Grid { page: 5, slot: 0 }, (4, 2)),
            "a not-yet-created page always fits -- dropping there grows a fresh one"
        );
        assert!(!layout.would_fit(HomeSlot::Dock { slot: 0 }, (2, 2)), "no dock cell ever fits a wider-than-1x1 span");
    }

    #[test]
    fn empty_trailing_pages_are_pruned_but_the_first_page_survives() {
        let mut layout = HomeLayout::empty(4);
        layout.place(HomeSlot::Grid { page: 0, slot: 0 }, HomeItem::app("a.desktop"), 4, false);
        layout.ensure_page(1, 4);
        layout.remove_slot(HomeSlot::Grid { page: 0, slot: 0 });
        assert_eq!(layout.page_count(), 1, "both pages were empty; only the first survives");
        layout.place(HomeSlot::Grid { page: 1, slot: 0 }, HomeItem::app("b.desktop"), 4, false);
        assert_eq!(layout.page_count(), 2, "page 1 now holds something");
        layout.remove_slot(HomeSlot::Grid { page: 1, slot: 0 });
        assert_eq!(layout.page_count(), 1, "trailing empty page 1 is pruned again");
    }
}
