#ifndef K230_VG_LITE_ACCESS_H
#define K230_VG_LITE_ACCESS_H
#include <vg_lite.h>
/* Duplicates a broker descriptor with CLOEXEC before any VG call.
 * Children lose both the descriptor and the GPU mapping at fork. */
vg_lite_error_t k230_vg_lite_adopt_device_fd(int fd);
#endif
