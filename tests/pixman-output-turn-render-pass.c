#define WLR_USE_UNSTABLE
#include <assert.h>
#include <drm_fourcc.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wlr/interfaces/wlr_buffer.h>
#include <wlr/render/pass.h>
#include <wlr/render/pixman.h>
#include <wlr/render/wlr_renderer.h>
#include <wlr/render/wlr_texture.h>
#include <wlr/util/transform.h>

enum { PHYSICAL_WIDTH = 28, PHYSICAL_HEIGHT = 18 };
enum { LOGICAL_WIDTH = PHYSICAL_HEIGHT, LOGICAL_HEIGHT = PHYSICAL_WIDTH };
enum { SOURCE_WIDTH = 7, SOURCE_HEIGHT = 5 };

struct mapped_buffer {
	struct wlr_buffer base;
	uint32_t format;
	uint8_t *data;
	size_t stride;
};

struct draw_case {
	const char *name;
	struct wlr_fbox src;
	struct wlr_box dst;
	enum wlr_scale_filter_mode filter;
	float alpha;
};

static const struct wlr_buffer_impl mapped_buffer_impl;

static struct mapped_buffer *mapped_buffer_from_base(struct wlr_buffer *base) {
	return (struct mapped_buffer *)base;
}

static void mapped_buffer_destroy(struct wlr_buffer *base) {
	struct mapped_buffer *buffer = mapped_buffer_from_base(base);
	wlr_buffer_finish(base);
	free(buffer->data);
	free(buffer);
}

static bool mapped_buffer_begin(struct wlr_buffer *base, uint32_t flags,
		void **data, uint32_t *format, size_t *stride) {
	struct mapped_buffer *buffer = mapped_buffer_from_base(base);
	(void)flags;
	*data = buffer->data;
	*format = buffer->format;
	*stride = buffer->stride;
	return true;
}

static void mapped_buffer_end(struct wlr_buffer *base) {
	(void)base;
}

static const struct wlr_buffer_impl mapped_buffer_impl = {
	.destroy = mapped_buffer_destroy,
	.begin_data_ptr_access = mapped_buffer_begin,
	.end_data_ptr_access = mapped_buffer_end,
};

static int format_cpp(uint32_t format) {
	return format == DRM_FORMAT_RGB565 ? 2 : 4;
}

static struct mapped_buffer *mapped_buffer_create(uint32_t format, int width, int height) {
	struct mapped_buffer *buffer = calloc(1, sizeof(*buffer));
	if (!buffer) return NULL;
	buffer->format = format;
	buffer->stride = (size_t)width * format_cpp(format);
	buffer->data = calloc((size_t)height, buffer->stride);
	if (!buffer->data) {
		free(buffer);
		return NULL;
	}
	wlr_buffer_init(&buffer->base, &mapped_buffer_impl, width, height);
	return buffer;
}

static uint16_t pack_rgb565(uint8_t red, uint8_t green, uint8_t blue) {
	return (uint16_t)(((red >> 3) << 11) | ((green >> 2) << 5) | (blue >> 3));
}

static void make_source(uint32_t format, uint8_t *data, size_t stride) {
	for (int y = 0; y < SOURCE_HEIGHT; y++) {
		for (int x = 0; x < SOURCE_WIDTH; x++) {
			uint8_t alpha = (x == 0 && y == 0) ? 255 :
				(x == SOURCE_WIDTH - 1 && y == 0) ? 176 :
				(x == 0 && y == SOURCE_HEIGHT - 1) ? 96 :
				(x == SOURCE_WIDTH - 1 && y == SOURCE_HEIGHT - 1) ? 224 :
				(uint8_t)(112 + ((x * 29 + y * 17) % 144));
			uint8_t red = (uint8_t)(23 + x * 31 + y * 7);
			uint8_t green = (uint8_t)(17 + y * 43 + x * 5);
			uint8_t blue = (uint8_t)(11 + x * 13 + y * 37);
			uint8_t *pixel = data + (size_t)y * stride + x * format_cpp(format);
			if (format == DRM_FORMAT_RGB565) {
				uint16_t value = pack_rgb565(red, green, blue);
				memcpy(pixel, &value, sizeof(value));
			} else {
				red = (uint8_t)((red * alpha + 127) / 255);
				green = (uint8_t)((green * alpha + 127) / 255);
				blue = (uint8_t)((blue * alpha + 127) / 255);
				uint32_t value = ((uint32_t)alpha << 24) | ((uint32_t)red << 16) |
					((uint32_t)green << 8) | blue;
				memcpy(pixel, &value, sizeof(value));
			}
		}
	}
}

static struct wlr_box physical_box(struct wlr_box logical,
		enum wl_output_transform transform) {
	struct wlr_box result;
	wlr_box_transform(&result, &logical, wlr_output_transform_invert(transform),
			LOGICAL_WIDTH, LOGICAL_HEIGHT);
	return result;
}

static void add_rect(struct wlr_render_pass *pass, struct wlr_box box,
		float red, float green, float blue, float alpha) {
	wlr_render_pass_add_rect(pass, &(struct wlr_render_rect_options){
		.box = box,
		.color = {.r = red, .g = green, .b = blue, .a = alpha},
		.blend_mode = WLR_RENDER_BLEND_MODE_NONE,
	});
}

static bool render_one(struct wlr_renderer *renderer, struct wlr_texture *texture,
		uint32_t format, enum wl_output_transform transform, bool output_turn,
		const struct draw_case *test, uint8_t **pixels_out) {
	int width = PHYSICAL_WIDTH;
	int height = PHYSICAL_HEIGHT;
	struct mapped_buffer *buffer = mapped_buffer_create(format, width, height);
	if (!buffer) return false;
	struct wlr_render_pass *pass = wlr_renderer_begin_buffer_pass(renderer, &buffer->base,
		&(struct wlr_buffer_pass_options){
			.output_transform = output_turn ? transform : WL_OUTPUT_TRANSFORM_NORMAL,
		});
	if (!pass) {
		wlr_buffer_drop(&buffer->base);
		return false;
	}
	struct wlr_box full = output_turn ? (struct wlr_box){0, 0, LOGICAL_WIDTH, LOGICAL_HEIGHT} :
		(struct wlr_box){0, 0, PHYSICAL_WIDTH, PHYSICAL_HEIGHT};
	add_rect(pass, full, 0.08f, 0.12f, 0.20f, 1.0f);
	struct wlr_box destination = output_turn ? test->dst : physical_box(test->dst, transform);
	float alpha = test->alpha;
	wlr_render_pass_add_texture(pass, &(struct wlr_render_texture_options){
		.texture = texture,
		.src_box = test->src,
		.dst_box = destination,
		.alpha = &alpha,
		.transform = output_turn ? WL_OUTPUT_TRANSFORM_NORMAL : transform,
		.filter_mode = test->filter,
		.blend_mode = WLR_RENDER_BLEND_MODE_PREMULTIPLIED,
	});
	struct wlr_box overlay = {.x = 8, .y = 10, .width = 3, .height = 4};
	if (!output_turn) overlay = physical_box(overlay, transform);
	add_rect(pass, overlay, 0.9f, 0.18f, 0.04f, 1.0f);
	if (!wlr_render_pass_submit(pass)) {
		wlr_buffer_drop(&buffer->base);
		return false;
	}
	*pixels_out = malloc(buffer->stride * (size_t)height);
	if (!*pixels_out) {
		wlr_buffer_drop(&buffer->base);
		return false;
	}
	memcpy(*pixels_out, buffer->data, buffer->stride * (size_t)height);
	wlr_buffer_drop(&buffer->base);
	return true;
}

static bool compare(const uint8_t *baseline, const uint8_t *candidate,
		uint32_t format, const char *name, enum wl_output_transform transform) {
	size_t bytes = (size_t)PHYSICAL_WIDTH * PHYSICAL_HEIGHT * format_cpp(format);
	size_t changed = 0;
	size_t changed_pixels = 0;
	unsigned max_channel_delta = 0;
	int min_x = PHYSICAL_WIDTH, min_y = PHYSICAL_HEIGHT, max_x = -1, max_y = -1;
	for (size_t i = 0; i < bytes; i++) {
		unsigned a = baseline[i], b = candidate[i];
		unsigned delta = a > b ? a - b : b - a;
		if (delta != 0) {
			changed++;
			int pixel = (int)(i / format_cpp(format));
			int x = pixel % PHYSICAL_WIDTH, y = pixel / PHYSICAL_WIDTH;
			if (x < min_x) min_x = x;
			if (x > max_x) max_x = x;
			if (y < min_y) min_y = y;
			if (y > max_y) max_y = y;
		}
	}
	for (size_t i = 0; i < bytes; i += format_cpp(format)) {
		unsigned a[4], b[4];
		if (format == DRM_FORMAT_RGB565) {
			uint16_t av, bv;
			memcpy(&av, baseline + i, sizeof(av));
			memcpy(&bv, candidate + i, sizeof(bv));
			a[0] = ((av >> 11) & 31) * 255 / 31;
			a[1] = ((av >> 5) & 63) * 255 / 63;
			a[2] = (av & 31) * 255 / 31;
			b[0] = ((bv >> 11) & 31) * 255 / 31;
			b[1] = ((bv >> 5) & 63) * 255 / 63;
			b[2] = (bv & 31) * 255 / 31;
		} else {
			uint32_t av, bv;
			memcpy(&av, baseline + i, sizeof(av));
			memcpy(&bv, candidate + i, sizeof(bv));
			for (int channel = 0; channel < 4; channel++) {
				a[channel] = (av >> (channel * 8)) & 255;
				b[channel] = (bv >> (channel * 8)) & 255;
			}
		}
		bool pixel_changed = false;
		for (int channel = 0; channel < (format == DRM_FORMAT_RGB565 ? 3 : 4); channel++) {
			unsigned delta = a[channel] > b[channel] ? a[channel] - b[channel] : b[channel] - a[channel];
			if (delta != 0) pixel_changed = true;
			if (delta > max_channel_delta) max_channel_delta = delta;
		}
		if (pixel_changed) changed_pixels++;
	}
	printf("format=%s transform=%d case=%s changed_bytes=%zu/%zu changed_pixels=%zu "
		"max_channel_delta_8bit=%u",
		format == DRM_FORMAT_RGB565 ? "RGB565" : "ARGB8888", transform, name,
		changed, bytes, changed_pixels, max_channel_delta);
	if (changed) printf(" mismatch_box=%d,%d-%d,%d", min_x, min_y, max_x, max_y);
	bool direction_ok = true;
	if (strcmp(name, "nearest-full") == 0) {
		int x = transform == WL_OUTPUT_TRANSFORM_90 ? 3 : 24;
		int y = transform == WL_OUTPUT_TRANSFORM_90 ? 15 : 2;
		uint8_t *pixel = (uint8_t *)candidate +
			((size_t)y * PHYSICAL_WIDTH + x) * format_cpp(format);
		if (format == DRM_FORMAT_RGB565) {
			uint16_t actual, expected = pack_rgb565(23, 17, 11);
			memcpy(&actual, pixel, sizeof(actual));
			direction_ok = actual == expected;
		} else {
			uint32_t actual, expected = 0xff17110b;
			memcpy(&actual, pixel, sizeof(actual));
			direction_ok = actual == expected;
		}
		printf(" direction_topleft_at=%d,%d:%s", x, y,
			direction_ok ? "expected" : "unexpected");
	}
	putchar('\n');
	return changed == 0 && direction_ok;
}

int main(void) {
	if (setenv("WLR_PIXMAN_OUTPUT_TURN", "1", 1) != 0) return 2;
	struct wlr_renderer *renderer = wlr_pixman_renderer_create();
	if (!renderer || !renderer->features.output_transform) {
		fprintf(stderr, "Pixman output-turn feature did not initialize\n");
		return 2;
	}
	const struct draw_case cases[] = {
		{"nearest-full", {0, 0, 0, 0}, {2, 3, 7, 5}, WLR_SCALE_FILTER_NEAREST, 1.0f},
		{"bilinear-scale", {0, 0, 0, 0}, {2, 3, 11, 13}, WLR_SCALE_FILTER_BILINEAR, 1.0f},
		{"bilinear-crop-alpha", {1, 1, 5, 3}, {4, 5, 9, 8},
			WLR_SCALE_FILTER_BILINEAR, 0.63f},
	};
	const uint32_t formats[] = {DRM_FORMAT_ARGB8888, DRM_FORMAT_RGB565};
	const enum wl_output_transform transforms[] = {
		WL_OUTPUT_TRANSFORM_90, WL_OUTPUT_TRANSFORM_270,
	};
	int failures = 0;
	for (size_t f = 0; f < sizeof(formats) / sizeof(formats[0]); f++) {
		uint32_t format = formats[f];
		size_t source_stride = ((size_t)SOURCE_WIDTH * format_cpp(format) + 3) & ~(size_t)3;
		uint8_t *source = malloc(source_stride * SOURCE_HEIGHT);
		if (!source) return 2;
		make_source(format, source, source_stride);
		struct wlr_texture *texture = wlr_texture_from_pixels(renderer, format,
			source_stride, SOURCE_WIDTH, SOURCE_HEIGHT, source);
		free(source);
		if (!texture) {
			fprintf(stderr, "could not create Pixman texture for format 0x%08x\n", format);
			wlr_renderer_destroy(renderer);
			return 2;
		}
		for (size_t t = 0; t < sizeof(transforms) / sizeof(transforms[0]); t++) {
			for (size_t c = 0; c < sizeof(cases) / sizeof(cases[0]); c++) {
				uint8_t *baseline = NULL, *candidate = NULL;
				if (!render_one(renderer, texture, format, transforms[t], false,
						&cases[c], &baseline) ||
					!render_one(renderer, texture, format, transforms[t], true,
						&cases[c], &candidate)) {
					fprintf(stderr, "render failed format=0x%08x transform=%d case=%s\n",
						format, transforms[t], cases[c].name);
					free(baseline);
					free(candidate);
					failures++;
					continue;
				}
				bool exact = compare(baseline, candidate, format, cases[c].name, transforms[t]);
				if (cases[c].filter == WLR_SCALE_FILTER_NEAREST && !exact) failures++;
				free(baseline);
				free(candidate);
			}
		}
		wlr_texture_destroy(texture);
	}
	wlr_renderer_destroy(renderer);
	return failures ? 1 : 0;
}
