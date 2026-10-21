"""Compile the real coverage callback with scene data and actual Pixman regions."""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WallpaperCover(unittest.TestCase):
    def test_full_viewport_and_conservative_exclusions(self):
        source = (ROOT / "nix/card-shell/adapter.c").read_text()
        callback = source[source.index("struct wallpaper_cover {"):
                          source.index("static void wallpaper_cover_publish(")]
        fixture = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <pixman.h>
enum { WL_OUTPUT_TRANSFORM_NORMAL, WL_OUTPUT_TRANSFORM_90 };
struct wlr_scene_tree;
struct wlr_scene_node { struct wlr_scene_tree *parent; };
struct wlr_scene_tree { struct wlr_scene_node node; };
struct wlr_buffer { int width, height; bool opaque; };
struct wlr_box { int x, y, width, height; };
struct wlr_fbox { double x, y, width, height; };
struct wlr_scene_buffer {
    struct wlr_scene_node node;
    struct wlr_buffer *buffer;
    float opacity;
    int transform, dst_width, dst_height, rounded_radius;
    struct wlr_fbox src_box;
    struct wlr_box rounded_clip;
    pixman_region32_t opaque_region;
};
struct sway_output {
    struct {
        struct wlr_scene_tree *shell_background, *shell_bottom, *tiling,
            *fullscreen, *shell_top, *shell_overlay;
    } layers;
};
static bool wlr_buffer_is_opaque(struct wlr_buffer *buffer) { return buffer->opaque; }
static bool wlr_box_empty(const struct wlr_box *box) {
    return box->width <= 0 || box->height <= 0;
}
'''
        checks = r'''
static bool covers(struct wallpaper_cover *cover, struct wlr_scene_buffer *b) {
    pixman_region32_clear(&cover->opaque);
    wallpaper_opaque_buffer(b, 0, 0, cover);
    pixman_box32_t frame = {0, 0, 1232, 568};
    return pixman_region32_contains_rectangle(&cover->opaque, &frame) == PIXMAN_REGION_IN;
}
int main(void) {
    struct wlr_scene_tree upper = {0}, lower = {0};
    struct sway_output output = {.layers = {.tiling = &upper, .shell_bottom = &lower}};
    struct wallpaper_cover cover = {.output = &output};
    pixman_region32_init(&cover.opaque);
    struct wlr_buffer buffer = {1232, 568, false};
    struct wlr_scene_buffer b = {
        .node = {.parent = &upper}, .buffer = &buffer, .opacity = 1,
        .dst_width = 1232, .dst_height = 568,
        .src_box = {0, 0, 1232, 568},
    };
    /* wlroots supplies an explicit full buffer source even with no crop.
     * ARGB client opacity is established by its logical opaque region. */
    pixman_region32_init_rect(&b.opaque_region, 0, 0, 1232, 568);
    assert(covers(&cover, &b));
    b.src_box = (struct wlr_fbox){0};
    assert(covers(&cover, &b));
    b.src_box = (struct wlr_fbox){0, 0, 1232, 568};
    pixman_region32_clear(&b.opaque_region);
    assert(!covers(&cover, &b));
    pixman_region32_union_rect(&b.opaque_region, &b.opaque_region, 0, 0, 1200, 568);
    assert(!covers(&cover, &b));
    pixman_region32_union_rect(&b.opaque_region, &b.opaque_region, 0, 0, 1232, 568);
    b.opacity = .5f;
    assert(!covers(&cover, &b));
    b.opacity = 1;
    b.transform = WL_OUTPUT_TRANSFORM_90;
    assert(!covers(&cover, &b));
    b.transform = WL_OUTPUT_TRANSFORM_NORMAL;
    b.src_box.x = 1;
    assert(!covers(&cover, &b));
    b.src_box = (struct wlr_fbox){0, 0, 1200, 568};
    assert(!covers(&cover, &b));
    b.src_box = (struct wlr_fbox){0, 0, 1232, 568};
    b.node.parent = &lower;
    assert(!covers(&cover, &b));
    b.node.parent = &upper;
    buffer.opaque = true;
    b.rounded_clip = (struct wlr_box){0, 0, 1232, 568};
    b.rounded_radius = 24;
    assert(!covers(&cover, &b));
    b.rounded_clip = (struct wlr_box){0};
    assert(covers(&cover, &b));
    b.dst_width = 0;
    assert(!covers(&cover, &b));
    pixman_region32_fini(&b.opaque_region);
    pixman_region32_fini(&cover.opaque);
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="wallpaper-cover-") as directory:
            p = Path(directory)
            (p / "cover.c").write_text(fixture + callback + checks)
            flags = shlex.split(subprocess.check_output(
                ["pkg-config", "--cflags", "--libs", "pixman-1"], text=True))
            subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra",
                            "-Werror", str(p / "cover.c"), *flags, "-o", str(p / "cover")],
                           check=True)
            subprocess.run([str(p / "cover")], check=True)


if __name__ == "__main__":
    unittest.main()
