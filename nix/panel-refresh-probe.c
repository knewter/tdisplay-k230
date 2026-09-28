/* Read-only DRM vblank sampler for the-card-deck-still-misses-its-frame-budget.
 *
 * Answers one narrow question without touching any hardware state: at what
 * rate does the kernel's own vblank IRQ (drm_crtc_handle_vblank(), which
 * drivers/gpu/drm/canaan/canaan_vo.c's canaan_vo_irq_handler() calls on every
 * VO_DISP_IRQ_STATUS interrupt -- see docs/evidence/card-shell/frame-budget/
 * analysis.md) actually fire, independent of whatever a compositor is doing?
 *
 * This program issues ONLY:
 *   - DRM_IOCTL_MODE_GETRESOURCES / GETCONNECTOR / GETENCODER / GETCRTC
 *     (via drmModeGetResources/GetConnector/GetEncoder/GetCrtc): read the
 *     currently programmed mode. No SETCRTC, no atomic commit.
 *   - DRM_IOCTL_WAIT_VBLANK, type DRM_VBLANK_RELATIVE, sequence 1 (via
 *     drmWaitVBlank()): block until the next vblank and report its sequence
 *     number and kernel timestamp. This is a query -- it never arms a page
 *     flip (DRM_VBLANK_FLIP is never set) and never requests an event
 *     (DRM_VBLANK_EVENT is never set), so it cannot change what is on the
 *     glass.
 *
 * It opens the DRM node without a mode-setting connection to it: it never
 * calls drmSetMaster, never becomes DRM master, and never touches a
 * framebuffer, plane, or CRTC property. If another process (the compositor)
 * already holds the display, this program does not contend with it -- both
 * GETRESOURCES/GETCONNECTOR/GETCRTC and a non-signalling WAIT_VBLANK are
 * available to any client with permission to open the node, master or not.
 *
 * Usage: panel-refresh-probe [/dev/dri/card0] [count]
 *   count defaults to 120 (about 2.3s at the panel's ~52.19Hz).
 *
 * Output, one tagged line per event, `PANEL_REFRESH v=1 event=... key=val ...`
 * -- see tools/parse-panel-refresh.py, which is the only thing that
 * interprets this format; keep the two in sync.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include <xf86drm.h>
#include <xf86drmMode.h>

static void print_mode(int fd)
{
	drmModeRes *res = drmModeGetResources(fd);
	if (!res) {
		printf("PANEL_REFRESH v=1 event=mode error=getresources_failed errno=%d\n", errno);
		return;
	}
	for (int i = 0; i < res->count_connectors; i++) {
		drmModeConnector *conn = drmModeGetConnector(fd, res->connectors[i]);
		if (!conn)
			continue;
		if (conn->connection != DRM_MODE_CONNECTED || !conn->encoder_id) {
			drmModeFreeConnector(conn);
			continue;
		}
		drmModeModeInfo mode;
		int have_mode = 0;
		drmModeEncoder *enc = drmModeGetEncoder(fd, conn->encoder_id);
		if (enc && enc->crtc_id) {
			drmModeCrtc *crtc = drmModeGetCrtc(fd, enc->crtc_id);
			if (crtc && crtc->mode_valid) {
				mode = crtc->mode;
				have_mode = 1;
			}
			if (crtc)
				drmModeFreeCrtc(crtc);
		}
		if (enc)
			drmModeFreeEncoder(enc);
		if (!have_mode && conn->count_modes > 0) {
			mode = conn->modes[0];
			have_mode = 1;
		}
		if (have_mode) {
			long vtotal_lines = mode.vtotal ? mode.vtotal : 1;
			double htotal_hz = mode.clock * 1000.0 / (mode.htotal ? mode.htotal : 1);
			double frame_hz = htotal_hz / vtotal_lines;
			printf("PANEL_REFRESH v=1 event=mode connector_id=%u name=%s "
			       "clock_khz=%u hdisplay=%u htotal=%u vdisplay=%u vtotal=%u "
			       "vrefresh_reported=%u vrefresh_computed_hz=%.4f\n",
			       conn->connector_id, mode.name[0] ? mode.name : "?",
			       mode.clock, mode.hdisplay, mode.htotal, mode.vdisplay,
			       mode.vtotal, mode.vrefresh, frame_hz);
		} else {
			printf("PANEL_REFRESH v=1 event=mode connector_id=%u error=no_mode\n",
			       conn->connector_id);
		}
		drmModeFreeConnector(conn);
	}
	drmModeFreeResources(res);
}

int main(int argc, char **argv)
{
	const char *dev = argc > 1 ? argv[1] : "/dev/dri/card0";
	int count = argc > 2 ? atoi(argv[2]) : 120;
	if (count <= 0)
		count = 120;

	/* O_RDWR is what the DRM node requires to accept ioctls at all; it is
	 * a POSIX open-mode flag, not a hardware write. No ioctl issued below
	 * sets a mode, plane, or property. */
	int fd = open(dev, O_RDWR | O_CLOEXEC);
	if (fd < 0) {
		fprintf(stderr, "panel-refresh-probe: open %s: %s\n", dev, strerror(errno));
		return 1;
	}

	printf("PANEL_REFRESH v=1 event=header device=%s requested_count=%d\n", dev, count);
	print_mode(fd);

	for (int i = 0; i < count; i++) {
		drmVBlank vbl;
		memset(&vbl, 0, sizeof(vbl));
		vbl.request.type = DRM_VBLANK_RELATIVE;
		vbl.request.sequence = 1;
		if (drmWaitVBlank(fd, &vbl) != 0) {
			printf("PANEL_REFRESH v=1 event=vblank_error errno=%d index=%d\n", errno, i);
			break;
		}
		printf("PANEL_REFRESH v=1 event=vblank seq=%u sec=%ld usec=%ld\n",
		       vbl.reply.sequence, vbl.reply.tval_sec, vbl.reply.tval_usec);
	}

	close(fd);
	return 0;
}
