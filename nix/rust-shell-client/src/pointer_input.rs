//! Primary pointer contacts share UI actions with touch, retaining surface ownership.
pub const PRIMARY_BUTTON: u32 = 0x110; // Linux BTN_LEFT, used by wl_pointer.
pub const POINTER_CONTACT_ID: i32 = i32::MIN; // Separate from physical touch IDs.

#[derive(Clone, Copy, Debug)]
pub enum Update {
    Press(u32),
    Motion,
    Release(u32),
    Leave,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Action {
    Down,
    Motion,
    Up,
    Cancel,
}

#[derive(Debug)]
pub struct PointerContact<S> {
    owner: Option<S>,
}

impl<S> Default for PointerContact<S> {
    fn default() -> Self { Self { owner: None } }
}

impl<S: PartialEq> PointerContact<S> {
    pub fn cancel(&mut self) -> Option<Action> {
        self.owner.take().map(|_| Action::Cancel)
    }

    pub fn update(&mut self, surface: S, update: Update) -> Option<Action> {
        match update {
            Update::Press(PRIMARY_BUTTON) if self.owner.is_none() => {
                self.owner = Some(surface);
                Some(Action::Down)
            }
            Update::Motion if self.owner.as_ref() == Some(&surface) => Some(Action::Motion),
            Update::Release(PRIMARY_BUTTON) => self.owner.take().map(|owner| {
                if owner == surface { Action::Up } else { Action::Cancel }
            }),
            Update::Leave if self.owner.as_ref() == Some(&surface) => self.cancel(),
            _ => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hover_and_secondary_buttons_never_activate() {
        let mut contact = PointerContact::default();
        assert_eq!(contact.update(1, Update::Motion), None);
        assert_eq!(contact.update(1, Update::Press(0x111)), None);
        assert_eq!(contact.update(1, Update::Release(0x111)), None);
        assert_eq!(contact.update(1, Update::Release(PRIMARY_BUTTON)), None);
    }

    #[test]
    fn primary_press_drag_release_routes_once() {
        let mut contact = PointerContact::default();
        assert_eq!(contact.update(1, Update::Press(PRIMARY_BUTTON)), Some(Action::Down));
        assert_eq!(contact.update(1, Update::Press(PRIMARY_BUTTON)), None);
        assert_eq!(contact.update(1, Update::Motion), Some(Action::Motion));
        assert_eq!(contact.update(1, Update::Release(0x111)), None);
        assert_eq!(contact.update(1, Update::Release(PRIMARY_BUTTON)), Some(Action::Up));
        assert_eq!(contact.update(1, Update::Release(PRIMARY_BUTTON)), None);
    }

    #[test]
    fn leave_and_capability_loss_cancel_without_activation() {
        let mut contact = PointerContact::default();
        contact.update(1, Update::Press(PRIMARY_BUTTON));
        assert_eq!(contact.update(2, Update::Leave), None);
        assert_eq!(contact.update(1, Update::Leave), Some(Action::Cancel));
        assert_eq!(contact.update(1, Update::Release(PRIMARY_BUTTON)), None);
        contact.update(1, Update::Press(PRIMARY_BUTTON));
        assert_eq!(contact.cancel(), Some(Action::Cancel));
        assert_eq!(contact.update(1, Update::Release(PRIMARY_BUTTON)), None);
    }

    #[test]
    fn a_different_surface_cannot_complete_the_click() {
        let mut contact = PointerContact::default();
        contact.update(1, Update::Press(PRIMARY_BUTTON));
        assert_eq!(contact.update(2, Update::Motion), None);
        assert_eq!(contact.update(2, Update::Release(PRIMARY_BUTTON)), Some(Action::Cancel));
        assert_eq!(contact.update(1, Update::Release(PRIMARY_BUTTON)), None);
    }
}
