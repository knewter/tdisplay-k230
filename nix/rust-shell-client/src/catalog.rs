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
            Some(AppEntry {
                id: app.id()?.to_string(),
                name: app.display_name().to_string(),
                icon: app
                    .icon()
                    .and_then(|icon| icon.to_string())
                    .map(|value| value.to_string()),
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
        assert!(apps.windows(2).all(|pair| {
            (pair[0].name.to_lowercase(), &pair[0].id) <= (pair[1].name.to_lowercase(), &pair[1].id)
        }));
    }
}
