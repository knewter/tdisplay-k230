# Pinned Omarchy theme helpers

Source: [`omacom/omarchy` at `28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`](https://github.com/omacom/omarchy/tree/28ceaae70ebac3a0edcc21f2faa77a90dc6d404c),
the inspected Quattro branch snapshot. `upstream/LICENSE` is MIT. The four
`upstream/bin` helpers and all 19 `upstream/default/themed` text templates are
copied from that revision. `SHA256SUMS.upstream` records each original byte
stream; `tests/test_omarchy_theme_tools.py` verifies every entry. No wallpaper,
theme clone, executable theme hook, or installer is redistributed here.

The sole source patch changes the first three assignments in
`omarchy-theme-set-templates` so explicit
`OMARCHY_THEME_TEMPLATES_DIR`, `OMARCHY_THEME_USER_TEMPLATES_DIR`, and
`OMARCHY_THEME_STAGING_DIR` override its old paths. Unset variables retain
upstream behavior. The byte manifest records the *pre-patch* helper; the host
test reconstructs and hashes that original script, then adjusts only its three
hardcoded path assignments in a reference harness to compare generated output
trees under disposable staging paths. No child `HOME` is changed. Runtime coordination must supply
an isolated stage and only publish declared outputs after validation; this
package alone does not accept or activate a community checkout.
