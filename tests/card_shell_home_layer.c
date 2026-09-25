/* Native host fixture for the QEMU compositor runtime, not a product client.
 *
 * Stands in for the real Home surface (nix/rust-shell-client's
 * always-mapped `Layer::Bottom` HomeSurface, see main.rs and
 * openspec/changes/the-shell-presents-a-pinned-home-screen/design.md
 * decision 1) without pulling in the Rust client's Wayland stack, catalog
 * loading, or on-disk state. Fills the whole output with a single opaque
 * colour unique to this fixture (`0xFF00FF00`, solid green) so a test can
 * tell "Home is visible" from "Home is hidden" with a plain pixel check,
 * and asks for the exact same layer/anchor/size shape the real surface
 * uses: `ZWLR_LAYER_SHELL_V1_LAYER_BOTTOM`, anchored to all four edges,
 * full output size, no exclusive zone, no keyboard interactivity. */
#define _POSIX_C_SOURCE 200809L
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <wayland-client.h>
#include "wlr-layer-shell-unstable-v1-client-protocol.h"

static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct zwlr_layer_shell_v1 *layer_shell;
static struct wl_surface *surface;
static bool configured;

static void global(void *data, struct wl_registry *registry, uint32_t name,
		const char *interface, uint32_t version) {
	(void)data;
	if (!strcmp(interface, wl_compositor_interface.name))
		compositor = wl_registry_bind(registry, name, &wl_compositor_interface, 4);
	else if (!strcmp(interface, wl_shm_interface.name))
		shm = wl_registry_bind(registry, name, &wl_shm_interface, 1);
	else if (!strcmp(interface, zwlr_layer_shell_v1_interface.name))
		layer_shell = wl_registry_bind(registry, name, &zwlr_layer_shell_v1_interface,
			version < 4 ? version : 4);
}
static void removed(void *data, struct wl_registry *registry, uint32_t name) {
	(void)data; (void)registry; (void)name;
}
static const struct wl_registry_listener registry_listener = {global, removed};

static void configure(void *data, struct zwlr_layer_surface_v1 *layer,
		uint32_t serial, uint32_t width, uint32_t height) {
	(void)data;
	zwlr_layer_surface_v1_ack_configure(layer, serial);
	if (!width || !height || width > 4096 || height > 4096)
		exit(3);
	size_t bytes = (size_t)width * height * 4;
	const char *runtime = getenv("XDG_RUNTIME_DIR");
	if (!runtime)
		exit(3);
	char path[4096];
	if (snprintf(path, sizeof(path), "%s/home-shm-XXXXXX", runtime) >= (int)sizeof(path))
		exit(3);
	int fd = mkstemp(path);
	if (fd < 0)
		exit(3);
	unlink(path);
	if (ftruncate(fd, (off_t)bytes) != 0)
		exit(3);
	uint32_t *pixels = mmap(NULL, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
	if (pixels == MAP_FAILED)
		exit(3);
	for (size_t i = 0; i < (size_t)width * height; i++)
		pixels[i] = 0xFF00FF00; /* opaque green, unique to this fixture */
	munmap(pixels, bytes);
	struct wl_shm_pool *pool = wl_shm_create_pool(shm, fd, (int)bytes);
	struct wl_buffer *buffer = wl_shm_pool_create_buffer(pool, 0, (int)width,
		(int)height, (int)width * 4, WL_SHM_FORMAT_ARGB8888);
	wl_shm_pool_destroy(pool);
	close(fd);
	wl_surface_attach(surface, buffer, 0, 0);
	wl_surface_damage_buffer(surface, 0, 0, (int)width, (int)height);
	wl_surface_commit(surface);
	configured = true;
}
static void closed(void *data, struct zwlr_layer_surface_v1 *layer) {
	(void)data; (void)layer;
	exit(0);
}
static const struct zwlr_layer_surface_v1_listener layer_listener = {configure, closed};

int main(void) {
	struct wl_display *display = wl_display_connect(NULL);
	if (!display)
		return 2;
	struct wl_registry *registry = wl_display_get_registry(display);
	wl_registry_add_listener(registry, &registry_listener, NULL);
	if (wl_display_roundtrip(display) < 0 || !compositor || !shm || !layer_shell)
		return 2;
	surface = wl_compositor_create_surface(compositor);
	struct zwlr_layer_surface_v1 *layer = zwlr_layer_shell_v1_get_layer_surface(
		layer_shell, surface, NULL, ZWLR_LAYER_SHELL_V1_LAYER_BOTTOM,
		"k230-shell-home");
	zwlr_layer_surface_v1_add_listener(layer, &layer_listener, NULL);
	zwlr_layer_surface_v1_set_anchor(layer,
		ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP | ZWLR_LAYER_SURFACE_V1_ANCHOR_BOTTOM |
		ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT | ZWLR_LAYER_SURFACE_V1_ANCHOR_RIGHT);
	zwlr_layer_surface_v1_set_exclusive_zone(layer, 0);
	zwlr_layer_surface_v1_set_keyboard_interactivity(layer,
		ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_NONE);
	wl_surface_commit(surface);
	while (!configured && wl_display_dispatch(display) >= 0) {}
	if (!configured || wl_display_roundtrip(display) < 0)
		return 2;
	puts("home mapped");
	fflush(stdout);
	while (wl_display_dispatch(display) >= 0) {}
	return 0;
}
