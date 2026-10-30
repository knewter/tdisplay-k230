/*
 * Portable Game of Life engine shared by U-Boot stage 1, early Linux and the
 * optional Wayland continuation (openspec change
 * the-boot-shows-a-computational-game-of-life).
 *
 * Freestanding: only <stdint.h>, <stddef.h> and memcpy/memset.  No malloc, no
 * floating point, no endianness assumption (the state record is serialised
 * little-endian byte by byte).
 *
 * The grid is a torus of GOL_W x GOL_H cells.  Each cell is drawn as a
 * GOL_CELL_PX square, so one grid covers the 568x1232 panel scanout exactly.
 */
#ifndef GAME_OF_LIFE_H
#define GAME_OF_LIFE_H

#include <stddef.h>
#include <stdint.h>

#define GOL_CELL_PX 4u
#define GOL_W 142u
#define GOL_H 308u
#define GOL_ROW_BYTES ((GOL_W + 7u) / 8u)
#define GOL_GRID_BYTES (GOL_ROW_BYTES * GOL_H)
#define GOL_PANEL_W (GOL_W * GOL_CELL_PX)
#define GOL_PANEL_H (GOL_H * GOL_CELL_PX)

struct gol_grid {
	uint8_t bits[GOL_GRID_BYTES];
};

/* Rules (B3/S23, toroidal). */
int gol_get(const struct gol_grid *g, unsigned x, unsigned y);
void gol_set(struct gol_grid *g, unsigned x, unsigned y, int alive);
/* dst and src must be distinct objects. */
void gol_step(struct gol_grid *dst, const struct gol_grid *src);
unsigned gol_population(const struct gol_grid *g);

/* Deterministic default: xorshift32 soup from `seed` plus a centred
 * R-pentomino.  The same seed always yields the same grid on any target. */
void gol_seed_default(struct gol_grid *g, uint32_t seed);

/* Insert a south-east travelling glider whose 3x3 box is centred on (cx, cy).
 * Coordinates wrap.  Cells under the box are overwritten. */
void gol_insert_glider(struct gol_grid *g, unsigned cx, unsigned cy);

/* Map a panel pixel to its cell; returns 0 and leaves outputs untouched when
 * the pixel is outside the panel. */
int gol_pixel_to_cell(unsigned px, unsigned py, unsigned *cx, unsigned *cy);

/* FNV-1a 32-bit. */
#define GOL_FNV_INIT 0x811c9dc5u
uint32_t gol_fnv1a(const void *data, size_t len, uint32_t h);
uint32_t gol_grid_hash(const struct gol_grid *g);

/*
 * Rendering.  Draws every cell into a little-endian XRGB8888 (B,G,R,X bytes)
 * framebuffer whose rows are `stride_bytes` apart; the buffer holds
 * GOL_PANEL_H rows.  The frame hash covers visible pixels only.
 */
#define GOL_COLOR_ON 0x00e8f0ffu
#define GOL_COLOR_OFF 0x00000000u
void gol_render_xrgb(const struct gol_grid *g, void *fb, size_t stride_bytes);
/* Redraw only the cells that differ between `prev` (already on screen) and
 * `cur`; the result is identical to a full gol_render_xrgb(cur).  Returns the
 * number of cells redrawn.  Used by stage 1, where every store is expensive. */
unsigned gol_render_xrgb_diff(const struct gol_grid *prev, const struct gol_grid *cur,
			      void *fb, size_t stride_bytes);
/* RGB565 variant for the Linux DRM owner (primary plane lacks XR24). */
void gol_render_rgb565(const struct gol_grid *g, void *fb, size_t stride_bytes);
uint32_t gol_frame_hash_xrgb(const void *fb, size_t stride_bytes);

/*
 * Versioned state record (little-endian on the wire):
 *   0  magic         0x4c33324b ("K23L" as bytes 4b 32 33 4c)
 *   4  abi_version   GOL_ABI_VERSION
 *   8  length        GOL_RECORD_BYTES
 *  12  boot_instance nonzero token chosen by stage 1 for this boot
 *  16  generation    generation of the stored grid
 *  20  seed          seed of the deterministic default
 *  24  width (u16)   GOL_W
 *  26  height (u16)  GOL_H
 *  28  cell_px (u8)  GOL_CELL_PX
 *  29  owner (u8)    enum gol_owner, who wrote it last
 *  30  reserved      0
 *  32  frame_generation  generation last drawn into the framebuffer
 *  36  checksum      FNV-1a over bytes [0,36) then the grid
 *  40  grid          GOL_GRID_BYTES
 */
#define GOL_RECORD_MAGIC 0x4c33324bu
#define GOL_ABI_VERSION 1u
#define GOL_RECORD_HEADER_BYTES 40u
#define GOL_RECORD_BYTES (GOL_RECORD_HEADER_BYTES + GOL_GRID_BYTES)

enum gol_owner {
	GOL_OWNER_NONE = 0,
	GOL_OWNER_UBOOT = 1,
	GOL_OWNER_LINUX = 2,
};

enum gol_status {
	GOL_OK = 0,
	GOL_BAD_MAGIC,
	GOL_BAD_VERSION,
	GOL_BAD_LENGTH,
	GOL_BAD_DIMENSIONS,
	GOL_BAD_CHECKSUM,
	GOL_BAD_INSTANCE, /* record is from another boot, or the token is zero */
};

struct gol_state {
	uint32_t boot_instance;
	uint32_t generation;
	uint32_t seed;
	uint32_t frame_generation;
	uint8_t owner;
	struct gol_grid grid;
};

void gol_state_init_default(struct gol_state *s, uint32_t boot_instance, uint32_t seed);
void gol_state_advance(struct gol_state *s);
/* `out` must hold GOL_RECORD_BYTES. */
void gol_record_encode(const struct gol_state *s, uint8_t *out);
/* `expect_instance` of 0 skips the same-boot comparison (host tooling). */
enum gol_status gol_record_decode(struct gol_state *s, const uint8_t *buf, size_t len,
				  uint32_t expect_instance);
const char *gol_status_name(enum gol_status st);

#endif
