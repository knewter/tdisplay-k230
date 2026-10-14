//! The non-focus-taking notification banner: a small card at the top of the
//! output that shows the broker's `preview` object while it reports one.
//!
//! This module owns only the pure parts (geometry, hit rect, text choice);
//! `render::RendererCache::draw_notification_banner` paints it and `main.rs`
//! maps it as a `Layer::Overlay` surface with `KeyboardInteractivity::None`.
//! The broker (`tools/notification_center.py`) has already applied its
//! privacy rules to the preview, so text is taken from the preview only and
//! never rebuilt from history rows.
use crate::service_data::NotificationPreview;

/// Gap between the output's top edge and the banner.
pub const TOP_MARGIN: f64 = 10.0;
pub const HEIGHT: f64 = 64.0;
/// Minimum gap to each side edge.
pub const SIDE_MARGIN: f64 = 12.0;
/// The banner never grows wider than this, so landscape stays a card.
pub const MAX_WIDTH: f64 = 640.0;
pub const GENERIC_SUMMARY: &str = "New notification";
pub const GENERIC_SOURCE: &str = "Notification";

/// The banner rectangle in output coordinates.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct BannerGeometry {
    pub left: f64,
    pub top: f64,
    pub width: f64,
    pub height: f64,
}

impl BannerGeometry {
    pub fn contains(&self, x: f64, y: f64) -> bool {
        (self.left..self.left + self.width).contains(&x)
            && (self.top..self.top + self.height).contains(&y)
    }
}

/// Banner rectangle for an output of the given size, horizontally centred.
pub fn banner_geometry(output_w: f64, _output_h: f64) -> BannerGeometry {
    let width = (output_w - 2.0 * SIDE_MARGIN).clamp(1.0, MAX_WIDTH);
    BannerGeometry { left: ((output_w - width) / 2.0).floor(), top: TOP_MARGIN, width, height: HEIGHT }
}

/// The surface size (width, height) and top margin the layer surface uses;
/// the surface is exactly the banner, so its local hit rect starts at 0,0.
pub fn surface_size(output_w: f64, output_h: f64) -> (u32, u32, i32) {
    let g = banner_geometry(output_w, output_h);
    (g.width as u32, g.height as u32, g.top as i32)
}

/// Hit rect in the banner surface's own coordinates.
pub fn local_geometry(output_w: f64, output_h: f64) -> BannerGeometry {
    let g = banner_geometry(output_w, output_h);
    BannerGeometry { left: 0.0, top: 0.0, ..g }
}

/// (source line, summary line). Uses only what the preview exposes; an empty
/// field falls back to the generic text so a banner is never blank.
pub fn banner_text(preview: &NotificationPreview) -> (String, String) {
    let clean = |value: &str, fallback: &str| {
        let value = value.split_whitespace().collect::<Vec<_>>().join(" ");
        if value.is_empty() { fallback.to_string() } else { value }
    };
    (clean(&preview.source, GENERIC_SOURCE), clean(&preview.summary, GENERIC_SUMMARY))
}

/// Bounded size check for the banner's own surface. `lib::frame_bytes` is for
/// panel-sized surfaces (300..=2048 on both axes) and rejects a 64 px banner,
/// which is why the first board run never drew one.
pub fn frame_bytes(width: u32, height: u32) -> Option<usize> {
    if !(1..=2048).contains(&width) || !(1..=256).contains(&height) {
        return None;
    }
    usize::try_from(width).ok()?.checked_mul(usize::try_from(height).ok()?)?.checked_mul(4)
}

/// Whether the banner should be on screen: a preview exists, the shade (which
/// lists it) is not open, and the operator has not already tapped this one.
pub fn visible(preview: Option<&NotificationPreview>, shade_open: bool, tapped: Option<u64>) -> bool {
    preview.is_some_and(|p| !shade_open && tapped != Some(p.id))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::service_data::Priority;

    fn preview(source: &str, summary: &str) -> NotificationPreview {
        NotificationPreview { id: 7, source: source.into(), icon: None, summary: summary.into(), priority: Priority::Ordinary, ongoing: false }
    }

    #[test]
    fn banner_sized_surfaces_pass_the_banner_bound_but_not_the_panel_bound() {
        assert_eq!(frame_bytes(544, 64), Some(544 * 64 * 4));
        assert_eq!(frame_bytes(640, 64), Some(640 * 64 * 4));
        assert!(crate::frame_bytes(544, 64).is_none());
        assert!(frame_bytes(0, 64).is_none() && frame_bytes(640, 257).is_none());
    }

    #[test]
    fn portrait_banner_spans_the_width_minus_margins() {
        let g = banner_geometry(568.0, 1232.0);
        assert_eq!((g.left, g.top, g.width, g.height), (12.0, 10.0, 544.0, 64.0));
        assert_eq!(surface_size(568.0, 1232.0), (544, 64, 10));
    }

    #[test]
    fn landscape_banner_is_a_centred_capped_card() {
        let g = banner_geometry(1232.0, 568.0);
        assert_eq!((g.left, g.width), (296.0, 640.0));
        assert_eq!(g.left * 2.0 + g.width, 1232.0);
        assert_eq!(surface_size(1232.0, 568.0), (640, 64, 10));
    }

    #[test]
    fn hit_rect_is_the_banner_in_both_spaces() {
        let g = banner_geometry(568.0, 1232.0);
        assert!(g.contains(300.0, 40.0));
        assert!(!g.contains(300.0, 5.0));
        assert!(!g.contains(300.0, 74.0));
        assert!(!g.contains(11.0, 40.0));
        let local = local_geometry(1232.0, 568.0);
        assert!(local.contains(0.0, 0.0) && local.contains(639.0, 63.0));
        assert!(!local.contains(640.0, 10.0) && !local.contains(10.0, 64.0));
    }

    #[test]
    fn trusted_preview_text_is_shown_as_given() {
        assert_eq!(banner_text(&preview("Terminal", "Build done")), ("Terminal".into(), "Build done".into()));
    }

    #[test]
    fn private_preview_shows_only_the_brokers_generic_fields() {
        // The broker substitutes these for private senders; the banner must
        // show exactly them and nothing else.
        let p = preview("Notification", "New notification");
        assert_eq!(banner_text(&p), ("Notification".into(), "New notification".into()));
    }

    #[test]
    fn empty_summary_or_source_falls_back_to_generic_text() {
        assert_eq!(banner_text(&preview("", "  \n ")), (GENERIC_SOURCE.into(), GENERIC_SUMMARY.into()));
        assert_eq!(banner_text(&preview("A\nB", "x  y")).0, "A B");
    }

    #[test]
    fn visibility_follows_preview_shade_and_tap() {
        let p = preview("a", "b");
        assert!(visible(Some(&p), false, None));
        assert!(!visible(None, false, None));
        assert!(!visible(Some(&p), true, None));
        assert!(!visible(Some(&p), false, Some(7)));
        assert!(visible(Some(&p), false, Some(8)));
    }

    #[test]
    fn painted_banner_is_opaque_inside_and_clear_at_the_rounded_corner() {
        let (w, h, _) = surface_size(568.0, 1232.0);
        let mut canvas = vec![0u8; (w * h * 4) as usize];
        crate::render::RendererCache::default()
            .draw_notification_banner(&mut canvas, w, h, &preview("Terminal", "Done"))
            .unwrap();
        let alpha = |x: u32, y: u32| canvas[((y * w + x) * 4 + 3) as usize];
        assert_eq!(alpha(0, 0), 0);
        assert!(alpha(w / 2, h - 6) > 200);
        let mut short = vec![0u8; (w * h * 4) as usize];
        assert!(crate::render::RendererCache::default()
            .draw_notification_banner(&mut short[..10], w, h, &preview("a", "b"))
            .is_err());
    }
}
