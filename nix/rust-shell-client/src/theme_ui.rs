//! Touch-only theme chooser state. All command I/O belongs to `ThemeWorker`.
//! Preview is reversible; only an explicit Apply may request activation.

use crate::theme_catalog::{
    BackgroundKind, ThemeList, ThemePreview, ThemeReply, ThemeRequest, ThemeResponse,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ThemePage {
    Controls,
    List,
    Preview,
}

#[derive(Clone, Debug)]
pub struct ThemeView {
    pub page: ThemePage,
    pub list: Option<ThemeList>,
    pub preview: Option<ThemePreview>,
    pub pending: Option<ThemeRequest>,
    pub pending_id: Option<u64>,
    /// A failed background choice must not leave the previous Apply enabled.
    pub selection_error: bool,
    pub error: Option<String>,
    pub message: Option<String>,
    pub scroll: f64,
}

impl Default for ThemeView {
    fn default() -> Self {
        Self {
            page: ThemePage::Controls,
            list: None,
            preview: None,
            pending: None,
            pending_id: None,
            selection_error: false,
            error: None,
            message: None,
            scroll: 0.0,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ThemeIntent {
    Open,
    Back,
    Close,
    Theme(usize),
    Background(usize),
    Apply,
}

const THEME_TOP: f64 = 204.0;
const THEME_ROW: f64 = 92.0;
const BACKGROUND_TOP: f64 = 662.0;
const BACKGROUND_ROW: f64 = 78.0;

impl ThemeView {
    pub fn open(&mut self) -> ThemeRequest {
        self.page = ThemePage::List;
        self.preview = None;
        self.selection_error = false;
        self.error = None;
        self.message = None;
        self.scroll = 0.0;
        ThemeRequest::List
    }

    pub fn back(&mut self) -> Option<ThemeRequest> {
        if matches!(self.pending, Some(ThemeRequest::Activate { .. })) {
            return None; // Activation cannot be cancelled after dispatch.
        }
        self.pending = None; // A late preview/activation reply must not reopen a dismissed view.
        self.pending_id = None;
        self.selection_error = false;
        self.error = None;
        self.message = None;
        self.scroll = 0.0;
        match self.page {
            ThemePage::Preview => {
                self.page = ThemePage::List;
                self.preview = None;
                Some(ThemeRequest::List)
            }
            ThemePage::List => {
                self.page = ThemePage::Controls;
                None
            }
            ThemePage::Controls => None,
        }
    }

    pub fn submitted(&mut self, request: ThemeRequest, id: u64) {
        if matches!(
            &request,
            ThemeRequest::Preview {
                background_id: Some(_),
                ..
            }
        ) {
            self.selection_error = true;
        }
        self.pending = Some(request);
        self.pending_id = Some(id);
        self.error = None;
        self.message = None;
    }

    pub fn failed_to_submit(&mut self, error: &str) {
        self.error = Some(error.into());
    }

    pub fn selection_failed(&mut self, error: &str) {
        self.selection_error = true;
        self.failed_to_submit(error);
    }

    pub fn accept(&mut self, reply: ThemeReply) -> bool {
        if self.pending_id != Some(reply.id) || self.pending.as_ref() != Some(&reply.request) {
            return false;
        }
        self.pending = None;
        self.pending_id = None;
        let was_background_choice = matches!(
            &reply.request,
            ThemeRequest::Preview {
                background_id: Some(_),
                ..
            }
        );
        match reply.result {
            Err(error) => {
                if was_background_choice {
                    self.selection_error = true;
                }
                self.error = Some(error);
            }
            Ok(ThemeResponse::List(list)) => {
                self.list = Some(list);
                self.page = ThemePage::List;
                self.error = None;
            }
            Ok(ThemeResponse::Preview(preview)) => {
                self.message = if preview.activated {
                    Some(match preview.app_appearance.as_ref() {
                        Some(app) if app.state != "applied" => {
                            format!("Theme applied; app reload {}", app.state)
                        }
                        _ => "Theme applied".into(),
                    })
                } else {
                    None
                };
                self.preview = Some(*preview);
                self.selection_error = false;
                self.page = ThemePage::Preview;
                self.scroll = 0.0;
                self.error = None;
            }
        }
        true
    }

    pub fn preview_request(&self, index: usize) -> Option<ThemeRequest> {
        let theme = self.list.as_ref()?.themes.get(index)?;
        Some(ThemeRequest::Preview {
            theme_id: theme.id.clone(),
            background_id: None,
        })
    }

    pub fn background_request(&self, index: usize) -> Result<ThemeRequest, &'static str> {
        let preview = self.preview.as_ref().ok_or("Preview unavailable")?;
        let background = preview
            .backgrounds
            .get(index)
            .ok_or("Background unavailable")?;
        if background.kind == BackgroundKind::Video {
            return Err("Video playback is not available in this shell");
        }
        Ok(ThemeRequest::Preview {
            theme_id: preview.theme.id.clone(),
            background_id: Some(background.id.clone()),
        })
    }

    pub fn apply_request(&self) -> Result<ThemeRequest, &'static str> {
        let preview = self.preview.as_ref().ok_or("Preview unavailable")?;
        if self.pending.is_some() {
            return Err("Wait for theme preview");
        }
        if self.selection_error {
            return Err("Select an available background before applying");
        }
        let selected = preview.backgrounds.iter().find(|row| row.selected);
        if selected.is_some_and(|row| row.kind == BackgroundKind::Video) {
            return Err("Video playback is not available in this shell");
        }
        Ok(ThemeRequest::Activate {
            theme_id: preview.theme.id.clone(),
            expected_generation: preview.generation.clone(),
            background_id: selected.map(|row| row.id.clone()),
        })
    }

    pub fn max_scroll(&self, height: u32) -> f64 {
        match self.page {
            ThemePage::List => {
                let count = self.list.as_ref().map_or(0, |list| list.themes.len());
                (THEME_TOP + count as f64 * THEME_ROW - (f64::from(height) - 64.0)).max(0.0)
            }
            ThemePage::Preview => {
                let count = self
                    .preview
                    .as_ref()
                    .map_or(0, |item| item.backgrounds.len());
                (BACKGROUND_TOP + count as f64 * BACKGROUND_ROW - (f64::from(height) - 152.0))
                    .max(0.0)
            }
            ThemePage::Controls => 0.0,
        }
    }

    pub fn scroll_from(&mut self, origin: f64, dy: f64, height: u32) -> bool {
        let next = (origin - dy).clamp(0.0, self.max_scroll(height));
        if (next - self.scroll).abs() < 1.0 {
            return false;
        }
        self.scroll = next;
        true
    }

    pub fn hit(
        &self,
        start: (f64, f64),
        end: (f64, f64),
        width: u32,
        height: u32,
    ) -> Option<ThemeIntent> {
        let w = f64::from(width);
        let h = f64::from(height);
        let dx = end.0 - start.0;
        let dy = end.1 - start.1;
        if dx.abs() > 18.0 || dy.abs() > 18.0 {
            return None;
        }
        if matches!(self.pending, Some(ThemeRequest::Activate { .. })) {
            return None;
        }
        match self.page {
            ThemePage::Controls => {
                ((104.0..162.0).contains(&end.1) && end.0 > w - 185.0).then_some(ThemeIntent::Open)
            }
            ThemePage::List | ThemePage::Preview => {
                if end.1 < 104.0 {
                    return if end.0 < 190.0 {
                        Some(ThemeIntent::Back)
                    } else if end.0 > w - 150.0 {
                        Some(ThemeIntent::Close)
                    } else {
                        None
                    };
                }
                if self.pending.is_some() {
                    return None;
                }
                match self.page {
                    ThemePage::List if (THEME_TOP..h - 60.0).contains(&end.1) => {
                        let index = ((end.1 - THEME_TOP + self.scroll) / THEME_ROW) as usize;
                        (index < self.list.as_ref()?.themes.len())
                            .then_some(ThemeIntent::Theme(index))
                    }
                    ThemePage::Preview if (BACKGROUND_TOP..h - 152.0).contains(&end.1) => {
                        let index =
                            ((end.1 - BACKGROUND_TOP + self.scroll) / BACKGROUND_ROW) as usize;
                        (index < self.preview.as_ref()?.backgrounds.len())
                            .then_some(ThemeIntent::Background(index))
                    }
                    ThemePage::Preview if (h - 126.0..h - 40.0).contains(&end.1) => {
                        if end.0 < w / 2.0 {
                            Some(ThemeIntent::Back)
                        } else if self.selection_error {
                            None
                        } else {
                            Some(ThemeIntent::Apply)
                        }
                    }
                    _ => None,
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::theme_catalog::{
        ActiveTheme, AppAppearance, BackgroundChoice, Compatibility, ThemeEntry, ThemeOrigin,
    };
    use std::{collections::BTreeMap, path::PathBuf};

    fn id(ch: char) -> String {
        std::iter::repeat_n(ch, 24).collect()
    }
    fn preview() -> ThemePreview {
        ThemePreview {
            theme: ThemeEntry {
                id: id('a'),
                name: "Night".into(),
                label: "Night".into(),
                origin: ThemeOrigin::Builtin,
            },
            generation: id('b'),
            appearance_path: PathBuf::from("/tmp/generation/appearance.json"),
            palette: BTreeMap::from([("background".into(), "#101020".into())]),
            icon_theme: None,
            backgrounds: vec![
                BackgroundChoice {
                    id: id('c'),
                    label: "Still".into(),
                    kind: BackgroundKind::Image,
                    path: PathBuf::from("/tmp/still.png"),
                    selected: true,
                    decode_status: "unverified".into(),
                },
                BackgroundChoice {
                    id: id('d'),
                    label: "Motion".into(),
                    kind: BackgroundKind::Video,
                    path: PathBuf::from("/tmp/video.webm"),
                    selected: false,
                    decode_status: "unverified".into(),
                },
            ],
            compatibility: Compatibility {
                applied: vec![],
                unavailable: vec![],
                unknown: vec![],
            },
            activated: false,
            app_appearance: None,
        }
    }

    #[test]
    fn explicit_preview_apply_identity_and_video_limit() {
        let mut view = ThemeView::default();
        assert_eq!(
            view.hit((500.0, 130.0), (500.0, 130.0), 568, 1232),
            Some(ThemeIntent::Open)
        );
        let list_request = view.open();
        view.submitted(list_request.clone(), 1);
        let list = ThemeList {
            themes: vec![preview().theme],
            active: ActiveTheme {
                id: None,
                generation: None,
            },
        };
        assert!(view.accept(ThemeReply {
            id: 1,
            request: list_request,
            result: Ok(ThemeResponse::List(list))
        }));
        assert_eq!(
            view.hit((200.0, 240.0), (200.0, 240.0), 568, 1232),
            Some(ThemeIntent::Theme(0))
        );
        let request = view.preview_request(0).unwrap();
        view.submitted(request.clone(), 2);
        assert!(view.accept(ThemeReply {
            id: 2,
            request,
            result: Ok(ThemeResponse::Preview(Box::new(preview())))
        }));
        assert_eq!(
            view.apply_request().unwrap(),
            ThemeRequest::Activate {
                theme_id: id('a'),
                expected_generation: id('b'),
                background_id: Some(id('c'))
            }
        );
        assert!(view.background_request(1).is_err());
        assert_eq!(
            view.hit((430.0, 1160.0), (430.0, 1160.0), 568, 1232),
            Some(ThemeIntent::Apply)
        );
    }

    #[test]
    fn stale_reply_after_cancel_and_app_sync_status_are_explicit() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        view.submitted(
            ThemeRequest::Preview {
                theme_id: id('a'),
                background_id: None,
            },
            1,
        );
        view.back();
        assert!(!view.accept(ThemeReply {
            id: 1,
            request: ThemeRequest::Preview {
                theme_id: id('a'),
                background_id: None
            },
            result: Ok(ThemeResponse::Preview(Box::new(preview())))
        }));
        assert_eq!(view.page, ThemePage::Controls);
        view.page = ThemePage::Preview;
        let mut applied = preview();
        applied.activated = true;
        applied.app_appearance = Some(AppAppearance {
            state: "failed".into(),
            generation: Some(id('b')),
            error: Some("reload-failed".into()),
            kind: None,
        });
        let request = ThemeRequest::Activate {
            theme_id: id('a'),
            expected_generation: id('b'),
            background_id: Some(id('c')),
        };
        view.submitted(request.clone(), 2);
        assert!(view.accept(ThemeReply {
            id: 2,
            request,
            result: Ok(ThemeResponse::Preview(Box::new(applied)))
        }));
        assert_eq!(
            view.message.as_deref(),
            Some("Theme applied; app reload failed")
        );
    }

    #[test]
    fn scroll_is_bounded_and_activation_cannot_be_cancelled_mid_transaction() {
        let mut view = ThemeView {
            page: ThemePage::List,
            list: Some(ThemeList {
                themes: (0..20).map(|_| preview().theme).collect(),
                active: ActiveTheme {
                    id: None,
                    generation: None,
                },
            }),
            ..ThemeView::default()
        };
        assert!(view.scroll_from(0.0, -9000.0, 1232));
        assert_eq!(view.scroll, view.max_scroll(1232));
        assert_eq!(
            view.hit((200.0, 242.0), (200.0, 242.0), 568, 1232),
            Some(ThemeIntent::Theme(9))
        );
        assert_eq!(view.hit((200.0, 242.0), (200.0, 270.0), 568, 1232), None);
        view.page = ThemePage::Preview;
        view.preview = Some(preview());
        let activation = view.apply_request().unwrap();
        view.submitted(activation, 1);
        assert_eq!(view.back(), None);
        assert_eq!(view.page, ThemePage::Preview);
        assert_eq!(view.hit((430.0, 1160.0), (430.0, 1160.0), 568, 1232), None);
    }

    #[test]
    fn reopened_list_rejects_old_equal_request_and_failed_background_blocks_apply() {
        let mut view = ThemeView::default();
        let old_request = view.open();
        view.submitted(old_request.clone(), 1);
        view.back();
        let new_request = view.open();
        view.submitted(new_request.clone(), 2);
        let list = ThemeList {
            themes: vec![preview().theme],
            active: ActiveTheme {
                id: None,
                generation: None,
            },
        };
        assert!(!view.accept(ThemeReply {
            id: 1,
            request: old_request,
            result: Ok(ThemeResponse::List(list.clone())),
        }));
        assert_eq!(view.pending_id, Some(2));
        assert!(view.accept(ThemeReply {
            id: 2,
            request: new_request,
            result: Ok(ThemeResponse::List(list)),
        }));
        view.page = ThemePage::Preview;
        view.preview = Some(preview());
        let choice = view.background_request(0).unwrap();
        view.submitted(choice.clone(), 3);
        assert!(view.accept(ThemeReply {
            id: 3,
            request: choice,
            result: Err("background preparation failed".into()),
        }));
        assert!(view.selection_error);
        assert!(view.apply_request().is_err());
        assert_eq!(view.hit((430.0, 1160.0), (430.0, 1160.0), 568, 1232), None);
        let retry = view.background_request(0).unwrap();
        view.submitted(retry.clone(), 4);
        assert!(view.accept(ThemeReply {
            id: 4,
            request: retry,
            result: Ok(ThemeResponse::Preview(Box::new(preview()))),
        }));
        assert!(!view.selection_error);
        assert!(view.apply_request().is_ok());
    }
}
