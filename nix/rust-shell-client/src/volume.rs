//! Pure volume model: the Android-style perceptual curve a UI percent maps
//! through before it reaches PipeWire, mute-toggle semantics, and the
//! volume HUD's auto-hide/expand/drag timing.
//!
//! No cairo, no service types, no subprocess -- mirrors `slider.rs`'s own
//! split (`theme_carousel.rs` set the pattern first). `render.rs` paints
//! from these numbers; `main.rs`/`service_data.rs` own touch dispatch and
//! the actual `pipewire_ipc::set_volume_command`/`ServiceRequest::Volume*`
//! calls -- this shell keeps one persistent `pw-cli` child fed a command
//! per throttled write rather than spawning `wpctl` per change
//! (`pipewire_ipc.rs`'s own module doc explains why).

/// Android's Quick Settings volume slider does not hand its 0-100 UI
/// position to the audio HAL as a linear gain -- a linear mapping puts
/// most of the audible loudness change in the bottom quarter of the
/// track, because human loudness perception is roughly logarithmic. The
/// framework instead runs the fader position through a cubic taper
/// (`android.media.AudioService`'s volume-curve tables approximate this
/// same shape: a few dB per step near the top, much less near the
/// bottom) before converting to a linear gain. This module reproduces
/// that specific curve -- `linear = (percent/100)^3` -- rather than a
/// straight percent-to-linear map, so equal steps of the slider read as
/// roughly equal steps of loudness, the same feel Android's own slider
/// has. `wpctl set-volume` takes a linear 0.0-1.0 value (or a `%` of
/// it -- see `docs/evidence/volume/wpctl.md`), so this linear number, not
/// the raw percent, is what actually goes on the wire.
pub fn percent_to_linear(percent: u8) -> f64 {
    let p = f64::from(percent.min(100)) / 100.0;
    p * p * p
}

/// The same curve expressed in dB, purely for evidence/debugging output
/// (`docs/evidence/volume/`) -- nothing in this shell parses dB back into
/// a percent. `0%` is silence, `-inf` dB by definition, represented here
/// as `f64::NEG_INFINITY` rather than an arbitrary large negative number,
/// so a caller cannot mistake it for a real attenuation value.
pub fn percent_to_db(percent: u8) -> f64 {
    let linear = percent_to_linear(percent);
    if linear <= 0.0 {
        f64::NEG_INFINITY
    } else {
        20.0 * linear.log10()
    }
}

/// Inverse of `percent_to_linear`, for reading a real PipeWire node's
/// linear `channelVolumes` value back into a UI percent (e.g. after an
/// external app, `wpctl`, or a keyboard shortcut changes it) without
/// fighting the curve above -- round-tripping a value this module itself
/// set must land back on the same percent.
pub fn linear_to_percent(linear: f64) -> u8 {
    let clamped = linear.clamp(0.0, 1.0);
    (clamped.cbrt() * 100.0).round().clamp(0.0, 100.0) as u8
}

/// A slider that reaches true silence (floor `0`, unlike brightness's
/// `slider::MIN_PERCENT`) plus the separate mute flag Android's volume
/// panel shows as a speaker-icon toggle, independent of the level itself
/// -- muting and later unmuting must restore the same level, not reset it
/// to some default.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct VolumeState {
    /// The last non-zero level the user (or an external app) actually
    /// set. Never zero once any real level has been observed, so
    /// unmuting always has something to restore to.
    level: u8,
    muted: bool,
}

impl Default for VolumeState {
    fn default() -> Self {
        // A freshly-opened sheet before the first `RefreshSettings` reply
        // shows *something* plausible rather than a jarring silent 0.
        Self {
            level: 50,
            muted: false,
        }
    }
}

impl VolumeState {
    pub fn new(level: u8, muted: bool) -> Self {
        Self {
            level: level.min(100),
            muted,
        }
    }

    /// What the slider thumb and the live/authoritative write should
    /// actually show and send: `0` while muted, regardless of the
    /// remembered level, exactly like Android's panel (muted always
    /// paints an empty track, never a stale thumb position).
    pub fn displayed_percent(&self) -> u8 {
        if self.muted {
            0
        } else {
            self.level
        }
    }

    pub fn is_muted(&self) -> bool {
        self.muted
    }

    /// A drag or tap-to-jump on the track. Dragging to the very bottom
    /// (`0`) engages mute, matching Android's own slider (there is no
    /// separate "0% but not muted" state a person can reach by dragging --
    /// only the icon tap in `toggle_mute` can produce that, and only
    /// transiently until the next drag). Dragging anywhere above `0`
    /// always clears mute and remembers the new level.
    pub fn set_from_drag(&mut self, percent: u8) {
        let percent = percent.min(100);
        if percent == 0 {
            self.muted = true;
        } else {
            self.muted = false;
            self.level = percent;
        }
    }

    /// The speaker-icon tap: flips `muted` without touching the
    /// remembered level, so unmuting always restores exactly the level
    /// that was active before the mute, never a default.
    pub fn toggle_mute(&mut self) {
        self.muted = !self.muted;
    }

    /// Reconcile with a real read (an external change, or this shell's own
    /// commit read back) -- never inferred, always what PipeWire/
    /// WirePlumber actually reports. A reported `0` sets `muted` the same
    /// way a drag to the bottom does, so a genuinely-silent external sink
    /// (someone else muted it) shows as muted here too, not as a
    /// zero-but-unmuted slider.
    pub fn apply_external(&mut self, percent: u8, muted: bool) {
        let percent = percent.min(100);
        self.muted = muted || percent == 0;
        if percent > 0 {
            self.level = percent;
        }
    }
}

/// How long the HUD stays up after the last volume change before it
/// auto-hides -- task: "about 2-3s", Android's own volume panel default.
/// Picked at the middle of that range.
pub const HUD_AUTO_HIDE_MS: u64 = 2_500;

/// Whether the HUD, shown at `shown_at_ms` (a monotonic millisecond
/// timestamp, e.g. `Instant::elapsed().as_millis()`), is still visible at
/// `now_ms`. A drag or an external change re-showing the HUD simply calls
/// this again with a fresh `shown_at_ms` -- there is no separate "extend"
/// operation, matching how `slider::live_write_due` treats every touch
/// sample as its own fresh instant.
pub fn hud_visible(shown_at_ms: u64, now_ms: u64) -> bool {
    now_ms.saturating_sub(shown_at_ms) < HUD_AUTO_HIDE_MS
}

/// Milliseconds until the HUD would auto-hide from `now_ms`, or `0` if it
/// already should have. Lets the caller size its next poll wake instead of
/// busy-checking every idle tick (task: "event-driven updates only, no
/// polling" -- the render loop still wakes periodically for other
/// reasons, but this tells it precisely when the HUD itself next needs a
/// wake, rather than an arbitrary fixed interval).
pub fn hud_hide_in_ms(shown_at_ms: u64, now_ms: u64) -> u64 {
    HUD_AUTO_HIDE_MS.saturating_sub(now_ms.saturating_sub(shown_at_ms))
}

/// One sink or stream's icon state for the speaker glyph: muted/silent,
/// or one of three loudness steps, matching Android's own 3-bar/mute
/// speaker glyph set. A `0` level and an explicit mute read as the same
/// glyph (both are silent to look at) even though `VolumeState` keeps
/// them as distinct underlying state.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum IconState {
    Muted,
    Low,
    Medium,
    High,
}

pub fn icon_state(percent: u8, muted: bool) -> IconState {
    if muted || percent == 0 {
        IconState::Muted
    } else if percent < 34 {
        IconState::Low
    } else if percent < 67 {
        IconState::Medium
    } else {
        IconState::High
    }
}

impl VolumeState {
    pub fn icon_state(&self) -> IconState {
        icon_state(self.displayed_percent(), self.muted)
    }
}

/// Where a touch, drag, or graph event came from -- used by `main.rs` to
/// decide whether to show a toast, raise the HUD, or do neither. Mirrors
/// the brightness slider's own toast suppression (commit "Suppress the
/// brightness slider's own success toast"): a gesture the user is already
/// looking at (dragging the shade's own slider, or the Settings row)
/// never needs a toast or a second on-screen surface; an external change
/// (another app, a hardware key, a keyboard shortcut, `wpctl` from a
/// serial console) is the one case the HUD exists to surface.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum ChangeOrigin {
    /// The shade's or Settings' own slider/icon, already on screen.
    OwnSlider,
    /// A hardware/keyboard volume key, dispatched through Sway's bindsym.
    HardwareKey,
    /// Anything else moving the PipeWire graph (`pipewire_ipc`'s monitor
    /// saw a Props change this client did not itself just send).
    ExternalGraph,
}

impl ChangeOrigin {
    /// Whether this origin should raise the volume HUD. The shade/Settings
    /// slider is already visible feedback; a hardware key or an external
    /// app change is not, so those are the two that pop the HUD.
    pub fn raises_hud(self) -> bool {
        !matches!(self, ChangeOrigin::OwnSlider)
    }
}

/// The pill's default vertical center (a fraction of the panel height, 0
/// top .. 1 bottom) before any drag has repositioned it.
pub const HUD_DEFAULT_POSITION_FRACTION: f64 = 0.5;

/// The volume HUD's own visibility, expand, and drag-reposition state,
/// layered on top of `hud_visible`/`hud_hide_in_ms` above. Time is
/// milliseconds from the same monotonic clock those functions use.
pub struct Hud {
    shown_at_ms: Option<u64>,
    expanded: bool,
    /// The pill's vertical center, as a fraction of the panel height --
    /// draggable, per the task's "can be dragged". Starts centered.
    position_fraction: f64,
    drag_id: Option<i32>,
}

impl Default for Hud {
    fn default() -> Self {
        Self {
            shown_at_ms: None,
            expanded: false,
            position_fraction: HUD_DEFAULT_POSITION_FRACTION,
            drag_id: None,
        }
    }
}

impl Hud {
    pub fn new() -> Self {
        Self::default()
    }

    /// Raises the HUD (or keeps it up) and resets its auto-hide timer.
    /// Never changes the expand state on its own -- an external change
    /// while the panel is already expanded should not silently collapse
    /// it back to the pill.
    pub fn show(&mut self, now_ms: u64) {
        self.shown_at_ms = Some(now_ms);
    }

    /// Whether the HUD should be painted at all right now. `render.rs`
    /// should call this before doing any HUD drawing work at all -- the
    /// cost rule is "render the HUD only while visible", so a `false`
    /// here means zero HUD-related cairo calls that frame.
    pub fn is_visible(&self, now_ms: u64) -> bool {
        match self.shown_at_ms {
            None => false,
            Some(shown_at) => hud_visible(shown_at, now_ms),
        }
    }

    /// Milliseconds until this HUD's own auto-hide, or `0` once it is
    /// already hidden/was never shown -- lets the event loop schedule its
    /// next wake precisely instead of polling every idle tick.
    pub fn hide_in_ms(&self, now_ms: u64) -> u64 {
        match self.shown_at_ms {
            None => 0,
            Some(shown_at) => hud_hide_in_ms(shown_at, now_ms),
        }
    }

    pub fn is_expanded(&self) -> bool {
        self.expanded
    }

    /// The "..." affordance: expands (or collapses) the panel and keeps
    /// it visible a full timer's worth longer, same as any other touch
    /// on the HUD.
    pub fn toggle_expand(&mut self, now_ms: u64) {
        self.expanded = !self.expanded;
        self.show(now_ms);
    }

    pub fn collapse(&mut self, now_ms: u64) {
        self.expanded = false;
        self.show(now_ms);
    }

    pub fn position_fraction(&self) -> f64 {
        self.position_fraction
    }

    /// Arms a drag of the pill itself, owned by touch `id` -- the same
    /// id-ownership convention `slider::Drag`/`Carousel`/`PanelClose`
    /// already use, so a second, stray touch can never move a
    /// reposition drag it did not start, and the shade's own close-drag
    /// never gets stolen by (or steals) a HUD reposition.
    pub fn start_drag(&mut self, id: i32, now_ms: u64) {
        self.drag_id = Some(id);
        self.show(now_ms);
    }

    pub fn drag_owner(&self) -> Option<i32> {
        self.drag_id
    }

    /// Moves the pill to `fraction` (already clamped to the panel by the
    /// caller's own geometry, but clamped again here defensively) and
    /// keeps the HUD visible. Only applied if `id` still owns the
    /// in-progress drag.
    pub fn drag_to(&mut self, id: i32, fraction: f64, now_ms: u64) {
        if self.drag_id != Some(id) {
            return;
        }
        self.position_fraction = fraction.clamp(0.0, 1.0);
        self.show(now_ms);
    }

    pub fn end_drag(&mut self, id: i32) {
        if self.drag_id == Some(id) {
            self.drag_id = None;
        }
    }
}

/// The collapsed pill's width and its margin from the panel's right edge
/// (task: "a vertical pill on the right edge").
pub const HUD_PILL_W: f64 = 64.0;
/// The expanded panel's own width -- Android's own expanded volume panel
/// is a wide card, not a tall thin pill; 64px has no room for an app name
/// next to its icon and slider (task: "per-stream volumes ... with the
/// app name and icon"). Still right-edge-anchored; only the left edge
/// moves further out.
pub const HUD_EXPANDED_W: f64 = 288.0;
pub const HUD_RIGHT_MARGIN: f64 = 16.0;
/// The collapsed pill's own height: enough for the speaker glyph, the
/// vertical fill bar, and the "..." expand affordance beneath it.
pub const HUD_COLLAPSED_H: f64 = 200.0;
/// One expanded-panel row's height (task: "each with its own slider,
/// like Android's expanded panel").
pub const HUD_ROW_H: f64 = 64.0;
/// Never let the pill (or its expanded panel) touch the very top/bottom
/// edge, dragged or not.
pub const HUD_MIN_EDGE_MARGIN: f64 = 16.0;

/// The HUD pill's on-screen rectangle, computed once from the panel size,
/// the pill's own (possibly dragged) vertical position, and how many
/// expanded rows (streams + sinks) it needs room for -- the single source
/// both `render.rs`'s paint and `main.rs`'s touch dispatch read, so the
/// two can never drift apart (the same discipline `slider::track_bounds`
/// already established for the sliders).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct HudGeometry {
    pub left: f64,
    pub top: f64,
    pub width: f64,
    pub height: f64,
    pub collapsed_h: f64,
}

pub fn hud_geometry(
    screen_w: f64,
    screen_h: f64,
    position_fraction: f64,
    expanded_row_count: usize,
) -> HudGeometry {
    let expanded_extra = if expanded_row_count > 0 {
        expanded_row_count as f64 * HUD_ROW_H + 12.0
    } else {
        0.0
    };
    let height = HUD_COLLAPSED_H + expanded_extra;
    let width = if expanded_row_count > 0 { HUD_EXPANDED_W } else { HUD_PILL_W };
    let center_y = position_fraction.clamp(0.0, 1.0) * screen_h;
    let max_top = (screen_h - height - HUD_MIN_EDGE_MARGIN).max(HUD_MIN_EDGE_MARGIN);
    let top = (center_y - height / 2.0).clamp(HUD_MIN_EDGE_MARGIN, max_top);
    HudGeometry {
        left: screen_w - width - HUD_RIGHT_MARGIN,
        top,
        width,
        height,
        collapsed_h: HUD_COLLAPSED_H,
    }
}

impl HudGeometry {
    pub fn contains(&self, x: f64, y: f64) -> bool {
        (self.left..self.left + self.width).contains(&x)
            && (self.top..self.top + self.height).contains(&y)
    }

    /// The speaker glyph near the pill's own top -- the mute toggle,
    /// same convention as the shade/Settings slider's own icon.
    pub fn mute_icon_hit(&self, x: f64, y: f64) -> bool {
        self.contains(x, y) && y < self.top + 44.0
    }

    /// The "..." affordance at the bottom of the *collapsed* band --
    /// always at a fixed offset from the pill's own top, whether or not
    /// it is currently expanded, so tapping it toggles reliably either
    /// way.
    pub fn expand_affordance_hit(&self, x: f64, y: f64) -> bool {
        self.contains(x, y)
            && y >= self.top + self.collapsed_h - 28.0
            && y < self.top + self.collapsed_h
    }

    /// Which expanded-panel row (0-based, streams then sinks -- the same
    /// order `render.rs` paints them in) a touch at `y` falls into, or
    /// `None` if it lands in the collapsed band or outside the pill
    /// entirely.
    pub fn expanded_row_at(&self, x: f64, y: f64) -> Option<usize> {
        if !self.contains(x, y) || y < self.top + self.collapsed_h {
            return None;
        }
        Some(((y - (self.top + self.collapsed_h)) / HUD_ROW_H) as usize)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn percent_to_linear_is_cubic_not_linear() {
        assert_eq!(percent_to_linear(0), 0.0);
        assert_eq!(percent_to_linear(100), 1.0);
        // Halfway on the slider is one-eighth the linear gain, not a half --
        // the whole point of the curve.
        assert!((percent_to_linear(50) - 0.125).abs() < 1e-9);
        assert!((percent_to_linear(10) - 0.001).abs() < 1e-9);
    }

    #[test]
    fn percent_to_linear_clamps_above_100() {
        assert_eq!(percent_to_linear(200), 1.0);
    }

    #[test]
    fn percent_to_db_is_negative_infinity_at_silence_and_zero_at_full() {
        assert_eq!(percent_to_db(0), f64::NEG_INFINITY);
        assert!((percent_to_db(100) - 0.0).abs() < 1e-9);
        assert!(percent_to_db(50) < 0.0);
    }

    #[test]
    fn linear_to_percent_round_trips_percent_to_linear() {
        for percent in [0u8, 1, 10, 33, 50, 75, 99, 100] {
            let linear = percent_to_linear(percent);
            assert_eq!(linear_to_percent(linear), percent);
        }
    }

    #[test]
    fn linear_to_percent_clamps_out_of_range_input() {
        assert_eq!(linear_to_percent(-0.5), 0);
        assert_eq!(linear_to_percent(4.0), 100);
    }

    #[test]
    fn dragging_to_the_bottom_engages_mute_like_android() {
        let mut state = VolumeState::new(60, false);
        state.set_from_drag(0);
        assert!(state.is_muted());
        assert_eq!(state.displayed_percent(), 0);
    }

    #[test]
    fn dragging_above_zero_clears_mute_and_sets_the_level() {
        let mut state = VolumeState::new(0, true);
        state.set_from_drag(40);
        assert!(!state.is_muted());
        assert_eq!(state.displayed_percent(), 40);
    }

    #[test]
    fn icon_tap_toggles_mute_and_restores_the_remembered_level() {
        let mut state = VolumeState::new(70, false);
        state.toggle_mute();
        assert!(state.is_muted());
        assert_eq!(state.displayed_percent(), 0);
        state.toggle_mute();
        assert!(!state.is_muted());
        // Unmuting restores 70, not some default -- the level was never
        // touched by the mute toggle itself.
        assert_eq!(state.displayed_percent(), 70);
    }

    #[test]
    fn external_zero_reads_as_muted_not_a_silent_unmuted_slider() {
        let mut state = VolumeState::new(80, false);
        state.apply_external(0, false);
        assert!(state.is_muted());
        // The remembered level from before the external zero is kept,
        // matching the icon-tap unmute case.
        assert_eq!(state.level, 80);
    }

    #[test]
    fn external_nonzero_updates_the_level_and_mute_flag_directly() {
        let mut state = VolumeState::new(10, true);
        state.apply_external(65, false);
        assert!(!state.is_muted());
        assert_eq!(state.displayed_percent(), 65);
    }

    #[test]
    fn hud_visible_holds_for_about_two_and_a_half_seconds() {
        assert!(hud_visible(0, 0));
        assert!(hud_visible(0, HUD_AUTO_HIDE_MS - 1));
        assert!(!hud_visible(0, HUD_AUTO_HIDE_MS));
        assert!(!hud_visible(0, HUD_AUTO_HIDE_MS + 10_000));
    }

    #[test]
    fn hud_hide_in_ms_counts_down_to_zero_and_never_goes_negative() {
        assert_eq!(hud_hide_in_ms(0, 0), HUD_AUTO_HIDE_MS);
        assert_eq!(hud_hide_in_ms(0, HUD_AUTO_HIDE_MS - 100), 100);
        assert_eq!(hud_hide_in_ms(0, HUD_AUTO_HIDE_MS), 0);
        assert_eq!(hud_hide_in_ms(0, HUD_AUTO_HIDE_MS + 5_000), 0);
    }

    #[test]
    fn volume_state_default_is_a_plausible_unmuted_midpoint() {
        let state = VolumeState::default();
        assert!(!state.is_muted());
        assert_eq!(state.displayed_percent(), 50);
    }

    #[test]
    fn icon_state_reads_muted_at_zero_percent_even_when_not_flagged_muted() {
        assert_eq!(icon_state(0, false), IconState::Muted);
        assert_eq!(icon_state(50, true), IconState::Muted);
        assert_eq!(icon_state(1, false), IconState::Low);
        assert_eq!(icon_state(33, false), IconState::Low);
        assert_eq!(icon_state(34, false), IconState::Medium);
        assert_eq!(icon_state(66, false), IconState::Medium);
        assert_eq!(icon_state(67, false), IconState::High);
        assert_eq!(icon_state(100, false), IconState::High);
    }

    #[test]
    fn volume_state_icon_state_reflects_displayed_percent_not_the_remembered_level() {
        let mut state = VolumeState::new(80, false);
        assert_eq!(state.icon_state(), IconState::High);
        state.toggle_mute();
        // Muted must read as the Muted glyph even though the remembered
        // level (80) would otherwise read High.
        assert_eq!(state.icon_state(), IconState::Muted);
    }

    #[test]
    fn change_origin_only_the_own_slider_suppresses_the_hud() {
        assert!(!ChangeOrigin::OwnSlider.raises_hud());
        assert!(ChangeOrigin::HardwareKey.raises_hud());
        assert!(ChangeOrigin::ExternalGraph.raises_hud());
    }

    #[test]
    fn hud_is_hidden_until_shown_and_autohides_after_its_window() {
        let mut hud = Hud::new();
        assert!(!hud.is_visible(0));
        assert_eq!(hud.hide_in_ms(0), 0);
        hud.show(1_000);
        assert!(hud.is_visible(1_000));
        assert!(hud.is_visible(1_000 + HUD_AUTO_HIDE_MS - 1));
        assert!(!hud.is_visible(1_000 + HUD_AUTO_HIDE_MS));
        assert_eq!(hud.hide_in_ms(1_000), HUD_AUTO_HIDE_MS);
    }

    #[test]
    fn hud_toggle_expand_flips_state_and_refreshes_the_timer() {
        let mut hud = Hud::new();
        assert!(!hud.is_expanded());
        hud.toggle_expand(0);
        assert!(hud.is_expanded());
        assert!(hud.is_visible(0));
        hud.toggle_expand(0);
        assert!(!hud.is_expanded());
    }

    #[test]
    fn hud_collapse_forces_collapsed_and_keeps_visible() {
        let mut hud = Hud::new();
        hud.toggle_expand(0);
        assert!(hud.is_expanded());
        hud.collapse(10);
        assert!(!hud.is_expanded());
        assert!(hud.is_visible(10));
    }

    #[test]
    fn hud_drag_is_owned_by_the_touch_that_started_it() {
        let mut hud = Hud::new();
        assert_eq!(hud.position_fraction(), HUD_DEFAULT_POSITION_FRACTION);
        hud.start_drag(9, 0);
        assert_eq!(hud.drag_owner(), Some(9));
        // A stray second touch id (e.g. the shade's own close-drag) must
        // never move this drag.
        hud.drag_to(3, 0.9, 10);
        assert_eq!(hud.position_fraction(), HUD_DEFAULT_POSITION_FRACTION);
        hud.drag_to(9, 0.9, 10);
        assert_eq!(hud.position_fraction(), 0.9);
        hud.end_drag(9);
        assert_eq!(hud.drag_owner(), None);
    }

    #[test]
    fn hud_drag_to_clamps_the_position_fraction() {
        let mut hud = Hud::new();
        hud.start_drag(1, 0);
        hud.drag_to(1, -5.0, 0);
        assert_eq!(hud.position_fraction(), 0.0);
        hud.drag_to(1, 5.0, 0);
        assert_eq!(hud.position_fraction(), 1.0);
    }

    #[test]
    fn hud_geometry_sits_on_the_right_edge_and_clamps_within_the_screen() {
        let g = hud_geometry(568.0, 1232.0, 0.5, 0);
        assert_eq!(g.left, 568.0 - HUD_PILL_W - HUD_RIGHT_MARGIN);
        assert_eq!(g.height, HUD_COLLAPSED_H);
        assert!(g.top >= HUD_MIN_EDGE_MARGIN);
        assert!(g.top + g.height <= 1232.0 - HUD_MIN_EDGE_MARGIN + 0.001);
        // Dragged to the very top/bottom, the pill still clamps inside
        // the screen rather than running off either edge.
        let top_dragged = hud_geometry(568.0, 1232.0, 0.0, 0);
        assert_eq!(top_dragged.top, HUD_MIN_EDGE_MARGIN);
        let bottom_dragged = hud_geometry(568.0, 1232.0, 1.0, 0);
        assert!((bottom_dragged.top + bottom_dragged.height - (1232.0 - HUD_MIN_EDGE_MARGIN)).abs() < 0.001);
    }

    #[test]
    fn hud_geometry_grows_by_one_row_per_expanded_item() {
        let collapsed = hud_geometry(568.0, 1232.0, 0.5, 0);
        let expanded = hud_geometry(568.0, 1232.0, 0.5, 3);
        assert_eq!(expanded.height, collapsed.height + 3.0 * HUD_ROW_H + 12.0);
    }

    #[test]
    fn hud_geometry_widens_when_expanded_but_stays_anchored_to_the_right_edge() {
        let collapsed = hud_geometry(568.0, 1232.0, 0.5, 0);
        assert_eq!(collapsed.width, HUD_PILL_W);
        let expanded = hud_geometry(568.0, 1232.0, 0.5, 1);
        assert_eq!(expanded.width, HUD_EXPANDED_W);
        let right_edge = |g: &HudGeometry| g.left + g.width;
        assert_eq!(right_edge(&collapsed), 568.0 - HUD_RIGHT_MARGIN);
        assert_eq!(right_edge(&expanded), 568.0 - HUD_RIGHT_MARGIN);
    }

    #[test]
    fn hud_geometry_hit_zones_are_disjoint_and_bounded_to_the_pill() {
        let g = hud_geometry(568.0, 1232.0, 0.5, 2);
        let cx = g.left + g.width / 2.0;
        assert!(g.mute_icon_hit(cx, g.top + 10.0));
        assert!(!g.mute_icon_hit(cx, g.top + 100.0));
        assert!(g.expand_affordance_hit(cx, g.top + g.collapsed_h - 10.0));
        assert!(!g.expand_affordance_hit(cx, g.top + 10.0));
        // Outside the pill entirely, nothing hits.
        assert!(!g.contains(g.left - 5.0, g.top + 10.0));
        assert!(!g.mute_icon_hit(g.left - 5.0, g.top + 10.0));
        // Expanded rows start right after the collapsed band and advance
        // one `HUD_ROW_H` per row.
        assert_eq!(g.expanded_row_at(cx, g.top + g.collapsed_h + 1.0), Some(0));
        assert_eq!(
            g.expanded_row_at(cx, g.top + g.collapsed_h + HUD_ROW_H + 1.0),
            Some(1)
        );
        assert_eq!(g.expanded_row_at(cx, g.top + 10.0), None);
    }
}
