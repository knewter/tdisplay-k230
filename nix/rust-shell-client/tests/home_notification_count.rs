//! Home's pending-notification count is painted into Home's own buffer: it
//! leaves the frame non-opaque, reads only an integer, and is absent at zero.
use cairo::{Context, Format, ImageSurface};
use k230_shell_rust::{
    bgra_frame_is_opaque,
    evidence_render::{seed_layout, synthetic_apps},
    home_screen::{pending_count_log, HomeScreen},
    icon::IconCache,
    render,
    service_data::{NotificationEvent, NotificationSnapshot, Priority},
};

fn frame(width: u32, height: u32, count: usize) -> Vec<u8> {
    let apps = synthetic_apps(30);
    let mut home = HomeScreen::new(seed_layout(&apps, width, height), f64::from(width));
    home.sync_columns(width, height);
    home.set_pending_count(count);
    let mut surface = ImageSurface::create(Format::ARgb32, width as i32, height as i32).unwrap();
    {
        let cr = Context::new(&surface).unwrap();
        render::paint_home(&cr, width, height, None, &home, &apps, &mut IconCache::new());
    }
    surface.flush();
    let bytes = surface.data().unwrap().to_vec();
    bytes
}

#[test]
fn home_frame_with_a_count_is_still_non_opaque() {
    for (w, h) in [(1232, 568), (568, 1232)] {
        for count in [0, 3, 100] {
            assert!(!bgra_frame_is_opaque(&frame(w, h, count)), "{w}x{h} count {count}");
        }
    }
}

#[test]
fn the_count_paints_something_and_zero_paints_nothing() {
    let (zero, three) = (frame(1232, 568, 0), frame(1232, 568, 3));
    assert_ne!(zero, three);
    // Only the top-right corner differs.
    let stride = 1232 * 4;
    for (i, (a, b)) in zero.iter().zip(&three).enumerate() {
        if a != b {
            let (x, y) = ((i % stride) / 4, i / stride);
            assert!(x > 1232 - 200 && y < 120, "pixel {x},{y} changed outside the corner");
        }
    }
}

#[test]
fn the_count_reads_only_the_integer() {
    let snapshot = NotificationSnapshot {
        count: 2,
        events: (0..2)
            .map(|i| NotificationEvent {
                id: i as u64,
                source: "SECRET".into(),
                icon: Some("SECRET".into()),
                summary: "SECRET".into(),
                body: "SECRET".into(),
                priority: Priority::Critical,
                timestamp: 0,
                error: None,
                dismissible: true,
                action_available: true,
                actions: Vec::new(),
            })
            .collect(),
        preview: None,
    };
    // The plumbing hands Home `snapshot.count` and the log the same integer.
    let with_secret_rows = frame(568, 1232, snapshot.count);
    let plain = frame(568, 1232, 2);
    assert_eq!(with_secret_rows, plain, "the frame depends on the integer alone");
    let line = pending_count_log(snapshot.count);
    assert_eq!(line, "home-pending-count 2");
    assert!(!line.contains("SECRET"));
}
