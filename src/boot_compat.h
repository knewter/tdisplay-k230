/* Integer types for both hosted C and U-Boot (which builds with -nostdinc). */
#ifndef BOOT_COMPAT_H
#define BOOT_COMPAT_H
#ifdef __UBOOT__
#include <common.h>
#include <linux/types.h>
#else
#include <stddef.h>
#include <stdint.h>
#endif
#endif
