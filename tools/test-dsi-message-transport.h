/* Host test shim only. Production functions are extracted from kernel source. */
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <sys/types.h>
#include <pthread.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint32_t __le32;
#define BIT(n) (1U << (n))
#define GENMASK(h, l) ((~0U << (l)) & (~0U >> (31-(h))))
#define MIPI_DSI_MSG_REQ_ACK BIT(0)
#define MIPI_DSI_MSG_USE_LPM BIT(1)
#define min_t(t, a, b) ((t)(a) < (t)(b) ? (t)(a) : (t)(b))
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
#define le32_to_cpu(x) (x)
#else
#define le32_to_cpu(x) __builtin_bswap32(x)
#endif
#define dev_err(...) ((void)0)
