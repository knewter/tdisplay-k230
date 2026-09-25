#ifndef CARD_SHELL_RENDER_H
#define CARD_SHELL_RENDER_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <wlr/types/wlr_scene.h>
struct card_brush;
/* The one system font family used by every label this compositor draws.
 * nix/rust-shell-client/src/render.rs names the same literal
 * (render::FONT_FAMILY) for the drawer/shade/settings surfaces that
 * composite into the same frame as the deck, so the two renderers never
 * drift onto different fallback faces (finding P1-1 of
 * docs/design/webos-polish-review.md). nix/shell.nix ships only
 * pkgs.dejavu_fonts on the image, so this is the only face guaranteed
 * present; the old bare "sans" alias here depended on fontconfig's default
 * mapping instead of naming it. */
#define CARD_SHELL_FONT_FAMILY "DejaVu Sans"
enum card_label_weight { CARD_LABEL_REGULAR, CARD_LABEL_MEDIUM, CARD_LABEL_BOLD };
struct wlr_scene_buffer *card_label(struct wlr_scene_tree *tree, const char *text, int width,
									int height, int size);
struct wlr_scene_buffer *card_label_color(struct wlr_scene_tree *tree, const char *text,
		int width, int height, int size, uint32_t argb);
/* A third weight tier between the plain and bold faces `card_label_color`
 * draws (finding P1-1), for section-eyebrow-style chrome text. DejaVu Sans
 * ships only Book/Bold, so CARD_LABEL_MEDIUM is a synthesized partial
 * emboldening rather than a true medium instance -- an accepted
 * approximation given the image deliberately carries one font family. */
struct wlr_scene_buffer *card_label_weight(struct wlr_scene_tree *tree, const char *text,
		int width, int height, int size, uint32_t argb, enum card_label_weight weight);
/* A small rounded glyph badge (initial letter on a tinted backdrop),
 * matching the drawer's own icon-tile fallback treatment, for the card
 * header identity fix (finding P0-1). */
struct wlr_scene_buffer *card_icon_badge(struct wlr_scene_tree *tree, char letter, int size,
		uint32_t bg_argb, uint32_t fg_argb);
/* Real-icon-first header glyph: resolves icon_name through the installed
 * icon theme (nix/card-shell/icon.c) and falls back to card_icon_badge's
 * own letter-badge painting when it does not resolve. icon_name may be
 * NULL. */
struct wlr_scene_buffer *card_icon_header(struct wlr_scene_tree *tree, const char *icon_name,
		char fallback_letter, int size, uint32_t bg_argb, uint32_t fg_argb);
struct wlr_scene_buffer *card_brush_scene(struct wlr_scene_tree *tree,
		const struct card_brush *brush, int width, int height);
/* A rounded-rect card plate: the brush fill clipped to a rounded rectangle,
 * with an optional stroked rim (stroke_rgba[3] <= 0 or stroke_width <= 0
 * skips the stroke). Used for both the live-card bezel and the non-live
 * placeholder shape, so a themed brush colours either one (webOS-style card
 * fix: no full-bleed coloured plate behind a live snapshot). */
struct wlr_scene_buffer *card_plate_scene(struct wlr_scene_tree *tree,
		const struct card_brush *brush, int width, int height, double radius,
		const float stroke_rgba[4], double stroke_width);
void card_brush_solid_color(const struct card_brush *brush, float out[4]);
struct wlr_buffer *card_scaled_buffer_create(struct wlr_buffer *source, int width, int height);
size_t card_scaled_buffer_bytes(void);
void card_clip_buffer(struct wlr_scene_buffer *copy, struct wlr_scene_buffer *source, double scale,
					  int x, int y, int parent_x, int parent_y, struct wlr_box clip);
#endif
