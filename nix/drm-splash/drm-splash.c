/*
 * Hold the immutable stage-1 image in a KMS dumb buffer until a compositor
 * replaces it.  The K230 primary plane does not advertise XR24: default to
 * RG16 and convert the B,G,R,X asset, while allowing AR24 only when the
 * selected primary plane proves it supports that format.
 */
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#include <drm/drm.h>
#include <drm/drm_mode.h>
#include <drm_fourcc.h>
#include <xf86drm.h>
#include <xf86drmMode.h>

#define SPLASH_WIDTH 568
#define SPLASH_HEIGHT 1232
#define SPLASH_BYTES ((size_t)SPLASH_WIDTH * SPLASH_HEIGHT * 4)
#define PRIMARY_PLANE_TYPE 1
#define HANDOFF_POLL_NS 100000000L

static volatile sig_atomic_t handoff_requested;
static volatile sig_atomic_t stopping;

struct target {
    uint32_t connector_id;
    uint32_t crtc_id;
    uint32_t crtc_index;
    drmModeModeInfo mode;
};

struct buffer {
    uint32_t handle;
    uint32_t fb_id;
    uint32_t pitch;
    uint64_t size;
    void *map;
};

static void on_handoff(int unused) { (void)unused; handoff_requested = 1; }
static void on_stop(int unused) { (void)unused; stopping = 1; }

static void fail(const char *what) {
    fprintf(stderr, "k230-drm-splash: %s: %s\n", what, strerror(errno));
}

static int install_signals(void) {
    struct sigaction handoff = { .sa_handler = on_handoff };
    struct sigaction stop = { .sa_handler = on_stop };
    sigemptyset(&handoff.sa_mask);
    sigemptyset(&stop.sa_mask);
    if (sigaction(SIGUSR1, &handoff, NULL) || sigaction(SIGTERM, &stop, NULL) ||
        sigaction(SIGINT, &stop, NULL)) {
        fail("install signal handlers");
        return -1;
    }
    return 0;
}

static bool mode_is_preferred(const drmModeModeInfo *mode) {
    return (mode->type & DRM_MODE_TYPE_PREFERRED) != 0;
}

static int find_target(int fd, struct target *target) {
    drmModeRes *resources = drmModeGetResources(fd);
    if (!resources) { fail("get DRM resources"); return -1; }

    int result = -1;
    for (int i = 0; i < resources->count_connectors && result; ++i) {
        drmModeConnector *connector = drmModeGetConnector(fd, resources->connectors[i]);
        if (!connector)
            continue;
        if (connector->connection != DRM_MODE_CONNECTED || connector->count_modes == 0) {
            drmModeFreeConnector(connector);
            continue;
        }

        int preferred = 0;
        for (int m = 0; m < connector->count_modes; ++m)
            if (mode_is_preferred(&connector->modes[m])) { preferred = m; break; }

        for (int e = -1; e < connector->count_encoders && result; ++e) {
            uint32_t encoder_id = e < 0 ? connector->encoder_id : connector->encoders[e];
            if (!encoder_id || (e >= 0 && encoder_id == connector->encoder_id))
                continue;
            drmModeEncoder *encoder = drmModeGetEncoder(fd, encoder_id);
            if (!encoder)
                continue;
            for (int c = 0; c < resources->count_crtcs; ++c) {
                if (!(encoder->possible_crtcs & (1U << c)))
                    continue;
                target->connector_id = connector->connector_id;
                target->crtc_id = resources->crtcs[c];
                target->crtc_index = (uint32_t)c;
                target->mode = connector->modes[preferred];
                result = 0;
                break;
            }
            drmModeFreeEncoder(encoder);
        }
        drmModeFreeConnector(connector);
    }
    drmModeFreeResources(resources);
    if (result)
        fprintf(stderr, "k230-drm-splash: no connected connector with a usable CRTC\n");
    return result;
}

static bool is_primary_plane(int fd, drmModePlane *plane) {
    drmModeObjectProperties *properties = drmModeObjectGetProperties(
        fd, plane->plane_id, DRM_MODE_OBJECT_PLANE);
    if (!properties)
        return false;
    bool primary = false;
    for (uint32_t i = 0; i < properties->count_props; ++i) {
        drmModePropertyRes *property = drmModeGetProperty(fd, properties->props[i]);
        if (property && strcmp(property->name, "type") == 0 &&
            properties->prop_values[i] == PRIMARY_PLANE_TYPE)
            primary = true;
        if (property)
            drmModeFreeProperty(property);
    }
    drmModeFreeObjectProperties(properties);
    return primary;
}

static int verify_primary_format(int fd, const struct target *target, uint32_t format) {
    drmModePlaneRes *planes = drmModeGetPlaneResources(fd);
    if (!planes) { fail("get plane resources"); return -1; }
    int result = -1;
    for (uint32_t i = 0; i < planes->count_planes && result; ++i) {
        drmModePlane *plane = drmModeGetPlane(fd, planes->planes[i]);
        if (!plane)
            continue;
        if ((plane->possible_crtcs & (1U << target->crtc_index)) && is_primary_plane(fd, plane)) {
            for (uint32_t f = 0; f < plane->count_formats; ++f)
                if (plane->formats[f] == format) { result = 0; break; }
        }
        drmModeFreePlane(plane);
    }
    drmModeFreePlaneResources(planes);
    if (result)
        fprintf(stderr, "k230-drm-splash: selected primary plane lacks format %.4s\n", (char *)&format);
    return result;
}

static int read_asset(uint8_t **asset) {
    int fd = open(DEFAULT_ASSET, O_RDONLY | O_CLOEXEC);
    if (fd < 0) { fail("open immutable splash asset"); return -1; }
    struct stat st;
    if (fstat(fd, &st) || st.st_size != (off_t)SPLASH_BYTES) {
        fprintf(stderr, "k230-drm-splash: %s must be exactly %zu BGRX bytes\n", DEFAULT_ASSET, SPLASH_BYTES);
        close(fd);
        return -1;
    }
    *asset = malloc(SPLASH_BYTES);
    if (!*asset) { fail("allocate splash image"); close(fd); return -1; }
    size_t at = 0;
    while (at < SPLASH_BYTES) {
        ssize_t read_bytes = read(fd, *asset + at, SPLASH_BYTES - at);
        if (read_bytes <= 0) { if (read_bytes == 0) errno = EIO; fail("read splash asset"); free(*asset); close(fd); return -1; }
        at += (size_t)read_bytes;
    }
    close(fd);
    return 0;
}

static int make_buffer(int fd, uint32_t width, uint32_t height, uint32_t format, struct buffer *buffer) {
    struct drm_mode_create_dumb create = { .width = width, .height = height,
        .bpp = format == DRM_FORMAT_RGB565 ? 16 : 32 };
    if (drmIoctl(fd, DRM_IOCTL_MODE_CREATE_DUMB, &create)) { fail("create dumb buffer"); return -1; }
    buffer->handle = create.handle;
    buffer->pitch = create.pitch;
    buffer->size = create.size;
    uint32_t handles[4] = { create.handle };
    uint32_t pitches[4] = { create.pitch };
    uint32_t offsets[4] = { 0 };
    if (drmModeAddFB2(fd, width, height, format, handles, pitches, offsets, &buffer->fb_id, 0)) {
        fail("add dumb framebuffer"); return -1;
    }
    struct drm_mode_map_dumb map = { .handle = create.handle };
    if (drmIoctl(fd, DRM_IOCTL_MODE_MAP_DUMB, &map)) { fail("map dumb buffer"); return -1; }
    buffer->map = mmap(NULL, create.size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, map.offset);
    if (buffer->map == MAP_FAILED) { buffer->map = NULL; fail("mmap dumb buffer"); return -1; }
    return 0;
}

static void fill_buffer(struct buffer *buffer, const uint8_t *asset, uint32_t format) {
    for (uint32_t y = 0; y < SPLASH_HEIGHT; ++y) {
        uint8_t *row = (uint8_t *)buffer->map + (size_t)y * buffer->pitch;
        for (uint32_t x = 0; x < SPLASH_WIDTH; ++x) {
            const uint8_t *pixel = asset + ((size_t)y * SPLASH_WIDTH + x) * 4;
            if (format == DRM_FORMAT_RGB565) {
                uint16_t value = ((uint16_t)(pixel[2] >> 3) << 11) |
                    ((uint16_t)(pixel[1] >> 2) << 5) | (pixel[0] >> 3);
                ((uint16_t *)row)[x] = value;
            } else {
                uint8_t *out = row + (size_t)x * 4;
                out[0] = pixel[0]; out[1] = pixel[1]; out[2] = pixel[2]; out[3] = 0xff;
            }
        }
    }
}

static int write_ready(const char *path, const char *state) {
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
    if (fd < 0) { fail("write readiness file"); return -1; }
    size_t length = strlen(state);
    int result = write(fd, state, length) == (ssize_t)length && fsync(fd) == 0 ? 0 : -1;
    if (result) fail("flush readiness file");
    close(fd);
    return result;
}

static bool successor_has_replaced_framebuffer(int fd, uint32_t crtc_id, uint32_t splash_fb) {
    drmModeCrtc *crtc = drmModeGetCrtc(fd, crtc_id);
    if (!crtc)
        return false;
    bool replaced = crtc->buffer_id != 0 && crtc->buffer_id != splash_fb;
    drmModeFreeCrtc(crtc);
    return replaced;
}

/* A replacement CRTC buffer proves ours is no longer scanning out.  Only then
 * is it safe to remove the FB and destroy the dumb allocation explicitly. */
static void release_replaced_buffer(int fd, struct buffer *buffer) {
    if (buffer->map) {
        munmap(buffer->map, buffer->size);
        buffer->map = NULL;
    }
    if (buffer->fb_id) {
        if (drmModeRmFB(fd, buffer->fb_id))
            fail("remove replaced splash framebuffer");
        else
            buffer->fb_id = 0;
    }
    if (!buffer->fb_id && buffer->handle) {
        struct drm_mode_destroy_dumb destroy = { .handle = buffer->handle };
        if (drmIoctl(fd, DRM_IOCTL_MODE_DESTROY_DUMB, &destroy))
            fail("destroy replaced dumb buffer");
        else
            buffer->handle = 0;
    }
}

int main(int argc, char **argv) {
    uint32_t format = DRM_FORMAT_RGB565;
    const char *ready_file = NULL;
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--format") == 0 && i + 1 < argc) {
            const char *value = argv[++i];
            if (strcmp(value, "rg16") == 0) format = DRM_FORMAT_RGB565;
            else if (strcmp(value, "ar24") == 0) format = DRM_FORMAT_ARGB8888;
            else { fprintf(stderr, "usage: %s [--format rg16|ar24] --ready-file PATH\n", argv[0]); return 2; }
        } else if (strcmp(argv[i], "--ready-file") == 0 && i + 1 < argc) {
            ready_file = argv[++i];
        } else {
            fprintf(stderr, "usage: %s [--format rg16|ar24] --ready-file PATH\n", argv[0]);
            return 2;
        }
    }
    if (!ready_file) { fprintf(stderr, "k230-drm-splash: --ready-file is required\n"); return 2; }
    if (install_signals()) return 1;

    int fd = open("/dev/dri/card0", O_RDWR | O_CLOEXEC);
    if (fd < 0) { fail("open /dev/dri/card0"); return 1; }
    struct target target;
    struct buffer buffer = { 0 };
    uint8_t *asset = NULL;
    int result = 1;
    bool successor_seen = false;
    if (find_target(fd, &target) || verify_primary_format(fd, &target, format) ||
        read_asset(&asset) || make_buffer(fd, target.mode.hdisplay, target.mode.vdisplay, format, &buffer))
        goto out_before_modeset;
    if (target.mode.hdisplay != SPLASH_WIDTH || target.mode.vdisplay != SPLASH_HEIGHT) {
        fprintf(stderr, "k230-drm-splash: connected mode is %ux%u, splash is %ux%u\n",
            target.mode.hdisplay, target.mode.vdisplay, SPLASH_WIDTH, SPLASH_HEIGHT);
        goto out_before_modeset;
    }
    fill_buffer(&buffer, asset, format);
    if (drmModeSetCrtc(fd, target.crtc_id, buffer.fb_id, 0, 0, &target.connector_id, 1, &target.mode)) {
        fail("set splash mode");
        goto out_before_modeset;
    }
    fprintf(stderr, "k230-drm-splash: scanout fb %u on connector %u crtc %u as %.4s\n",
        buffer.fb_id, target.connector_id, target.crtc_id, (char *)&format);
    if (write_ready(ready_file, "scanout\n"))
        goto out_after_modeset;

    while (!stopping) {
        if (handoff_requested) {
            handoff_requested = 0;
            if (drmDropMaster(fd)) { fail("drop DRM master for shell handoff"); continue; }
            if (write_ready(ready_file, "master-dropped\n")) break;
            fprintf(stderr, "k230-drm-splash: DRM master dropped; retaining fb %u for successor\n", buffer.fb_id);
            while (!stopping) {
                if (successor_has_replaced_framebuffer(fd, target.crtc_id, buffer.fb_id)) {
                    fprintf(stderr, "k230-drm-splash: successor replaced fb %u; releasing owner\n", buffer.fb_id);
                    successor_seen = true;
                    result = 0;
                    goto out_after_modeset;
                }
                struct timespec pause = { .tv_nsec = HANDOFF_POLL_NS };
                nanosleep(&pause, NULL);
            }
        }
        struct timespec pause = { .tv_nsec = HANDOFF_POLL_NS };
        nanosleep(&pause, NULL);
    }
    fprintf(stderr, "k230-drm-splash: stopping without a successor; no explicit CRTC clear or framebuffer removal\n");

out_after_modeset:
    if (successor_seen)
        release_replaced_buffer(fd, &buffer);
    /* Without a successor, retain the KMS objects until service stop.  Do not
     * clear the CRTC or blindly remove an active framebuffer.  Close-time
     * lifetime remains driver-specific and task 5.4 must measure it. */
    result = result == 0 ? 0 : 1;
out_before_modeset:
    free(asset);
    if (buffer.map) munmap(buffer.map, buffer.size);
    close(fd);
    return result;
}
