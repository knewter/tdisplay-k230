//! Installed desktop entries, using GIO's visibility and Exec semantics.
use gio::prelude::*;

#[derive(Clone, Debug)]
pub struct AppEntry {
    pub id: String,
    pub name: String,
    pub icon: Option<String>,
}

pub fn installed_apps() -> Vec<AppEntry> {
    let mut apps: Vec<_> = gio::AppInfo::all()
        .into_iter()
        .filter(|app| app.should_show())
        .filter_map(|app| {
            let id = app.id()?.to_string();
            if id.is_empty() || id.len() > 160 {
                return None;
            }
            let name: String = app
                .display_name()
                .chars()
                .filter(|character| !character.is_control())
                .take(96)
                .collect();
            if name.trim().is_empty() {
                return None;
            }
            Some(AppEntry {
                id,
                name,
                icon: app
                    .icon()
                    .and_then(|icon| icon.to_string())
                    .map(|value| value.to_string())
                    .filter(|value| value.len() <= 512),
            })
        })
        .collect();
    apps.sort_by(|a, b| {
        a.name
            .to_lowercase()
            .cmp(&b.name.to_lowercase())
            .then(a.id.cmp(&b.id))
    });
    apps.truncate(128);
    apps
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn catalog_is_bounded_and_stably_sorted() {
        let apps = installed_apps();
        assert!(apps.len() <= 128);
        assert!(apps
            .iter()
            .all(|app| !app.id.is_empty() && !app.name.is_empty()));
        assert!(apps.iter().all(|app| app.id.len() <= 160
            && app.name.chars().count() <= 96
            && app.icon.as_ref().is_none_or(|icon| icon.len() <= 512)));
        assert!(apps.windows(2).all(|pair| {
            (pair[0].name.to_lowercase(), &pair[0].id) <= (pair[1].name.to_lowercase(), &pair[1].id)
        }));
    }
}
