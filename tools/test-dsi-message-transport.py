#!/usr/bin/env python3
"""Compile actual patched DSI transport against bounded mock MMIO (host-only).

Pass the realized kernel SOURCE from before or after this patch. The test copies
three files privately and applies the transport patch if needed. It extracts the
kernel's actual packet builder and host functions, not a Python reimplementation.
No Nix build, board, serial port or network is used.
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    match = re.search(r"^[\w *]+\b" + re.escape(name) + r"\([^;{]*?\n\{.*?^\}", source, re.M | re.S)
    if not match:
        raise RuntimeError(f"function not found: {name}")
    return match.group()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel_source", type=Path)
    args = parser.parse_args()
    source = args.kernel_source.resolve()
    with tempfile.TemporaryDirectory(prefix="k230-dsi-host-") as temp:
        temp = Path(temp)
        for name in ("canaan/canaan_dsi.c", "canaan/canaan_dsi.h", "panel/panel-canaan-universal.c"):
            relative = Path("drivers/gpu/drm") / name
            dest = temp / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, dest)
        driver = temp / "drivers/gpu/drm/canaan/canaan_dsi.c"
        if "canaan_dsi_write_packet" not in driver.read_text():
            subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i",
                            str(ROOT / "nix/patches/canaan-dsi-message-transport.patch")],
                           cwd=temp, check=True)
        text = driver.read_text()
        core = (source / "drivers/gpu/drm/drm_mipi_dsi.c").read_text()
        header = (source / "include/drm/drm_mipi_dsi.h").read_text()
        definitions = text[text.index("#define DSI_GEN_HDR"):text.index("#define TXPHY_445_5_M")]
        structures = "\n".join(re.search(r"struct " + name + r" \{.*?^\};", header, re.M | re.S).group()
                               for name in ("mipi_dsi_msg", "mipi_dsi_packet"))
        pieces = [Path(__file__).with_suffix(".h").read_text(),
                  (source / "include/video/mipi_display.h").read_text(), structures, definitions,
                  MOCK,
                  *[function(core, name) for name in ("mipi_dsi_packet_format_is_short",
                    "mipi_dsi_packet_format_is_long", "mipi_dsi_create_packet")],
                  *[function(text, name) for name in ("dsi_write", "dsi_read",
                    "canaan_dsi_message_config", "canaan_dsi_write_packet",
                    "canaan_dsi_read_response", "canaan_dsi_transfer")],
                  TESTS]
        (temp / "test.c").write_text("\n".join(pieces))
        subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-pthread",
                        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g",
                        str(temp / "test.c"), "-o", str(temp / "test")], check=True)
        subprocess.run([str(temp / "test")], check=True)


MOCK = r'''
struct mipi_dsi_host { int unused; };
struct canaan_dsi {
    unsigned char *base;
    struct mipi_dsi_host host;
    pthread_mutex_t transfer_lock;
    bool transfer_ready;
};
#define host_to_canaan_dsi(h) ((struct canaan_dsi *)((char *)(h) - offsetof(struct canaan_dsi, host)))
static u32 regs[256], statuses[128], payloads[4096], headers[2048];
static unsigned int status_count, status_index, status_reads, payload_count, header_count;
static unsigned int reads, writes;
static u32 default_status, response;
static bool reply_on_header;
static struct canaan_dsi dsi;

static void mutex_lock(pthread_mutex_t *mutex) { assert(pthread_mutex_lock(mutex) == 0); }
static void mutex_unlock(pthread_mutex_t *mutex) { assert(pthread_mutex_unlock(mutex) == 0); }
static u32 readl(const void *addr) {
    size_t offset = (const unsigned char *)addr - dsi.base;
    reads++;
    if (offset == DSI_CMD_PKT_STATUS) {
        status_reads++;
        return status_index < status_count ? statuses[status_index++] : default_status;
    }
    if (offset == DSI_GEN_PLD_DATA) return response;
    return regs[offset / 4];
}
static void writel(u32 value, void *addr) {
    size_t offset = (unsigned char *)addr - dsi.base;
    writes++;
    regs[offset / 4] = value;
    if (offset == DSI_GEN_HDR) {
        assert(header_count < 2048);
        headers[header_count++] = value;
        if (reply_on_header) default_status &= ~GEN_PLD_R_EMPTY;
    }
    if (offset == DSI_GEN_PLD_DATA) {
        assert(payload_count < 4096);
        payloads[payload_count++] = value;
    }
    /* A message must never toggle video mode, power or the PHY clock. */
    assert(offset != MODE_CFG && offset != LPCLK_CTRL && offset != 0x04);
}
#define readl_poll_timeout(addr, value, condition, delay, timeout) ({ \
    int poll_result = -ETIMEDOUT; \
    for (int poll_count = 0; poll_count < (timeout) / (delay) + 1; poll_count++) { \
        (value) = readl(addr); \
        if (condition) { poll_result = 0; break; } \
    } \
    poll_result; \
})
'''

TESTS = r'''
static unsigned int cases;
static const u8 brightness[] = { 0x51, 0xfe };
static struct mipi_dsi_msg msg;
static void reset(void) {
    memset(regs, 0, sizeof(regs));
    status_count = status_index = status_reads = payload_count = header_count = reads = writes = 0;
    default_status = GEN_CMD_EMPTY | GEN_PLD_W_EMPTY | GEN_PLD_R_EMPTY;
    response = 0x9c;
    reply_on_header = false;
    dsi.transfer_ready = true;
    regs[VID_MODE_CFG / 4] = 0x3f02;
    regs[CMD_MODE_CFG / 4] = 1;
    msg = (struct mipi_dsi_msg) {
        .type = MIPI_DSI_DCS_SHORT_WRITE_PARAM, .flags = MIPI_DSI_MSG_USE_LPM,
        .tx_buf = brightness, .tx_len = sizeof(brightness),
    };
    cases++;
}
static ssize_t transfer(void) { return canaan_dsi_transfer(&dsi.host, &msg); }
static void *writer(void *arg) {
    u8 bytes[] = { (uintptr_t)arg, 2, 3, 4, (uintptr_t)arg };
    struct mipi_dsi_msg threaded = {
        .type = MIPI_DSI_DCS_LONG_WRITE, .flags = MIPI_DSI_MSG_USE_LPM,
        .tx_buf = bytes, .tx_len = sizeof(bytes), .channel = (uintptr_t)arg,
    };
    for (int i = 0; i < 500; i++) assert(canaan_dsi_transfer(&dsi.host, &threaded) == 9);
    return NULL;
}
int main(void) {
    pthread_mutexattr_t attr;
    assert(!pthread_mutexattr_init(&attr));
    assert(!pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_ERRORCHECK));
    assert(!pthread_mutex_init(&dsi.transfer_lock, &attr));
    dsi.base = (unsigned char *)regs;
    reset();
    assert(transfer() == 4);
    assert(header_count == 1 && headers[0] == 0x00fe5115 && payload_count == 0);
    assert(regs[CMD_MODE_CFG / 4] == (CMD_MODE_ALL_LP | 1));
    assert(regs[VID_MODE_CFG / 4] == 0xbf02);
    assert(regs[DPI_LP_CMD_TIM / 4] == 0x100004);

    reset(); msg.channel = 3;
    assert(transfer() == 4 && headers[0] == 0x00fe51d5);
    reset(); msg.type = MIPI_DSI_DCS_SHORT_WRITE; msg.tx_len = 1;
    assert(transfer() == 4 && headers[0] == 0x5105 && !payload_count);
    reset(); msg.type = MIPI_DSI_GENERIC_SHORT_WRITE_2_PARAM;
    assert(transfer() == 4 && headers[0] == 0xfe5123 && !payload_count);
    reset(); msg.type = MIPI_DSI_DCS_LONG_WRITE;
    assert(transfer() == 6 && headers[0] == 0x239 && payload_count == 1 && payloads[0] == 0xfe51);
    reset(); u8 bytes[] = { 0x51, 1, 2, 3, 4 }; msg.type = MIPI_DSI_DCS_LONG_WRITE;
    msg.tx_buf = bytes; msg.tx_len = sizeof(bytes);
    assert(transfer() == 9 && headers[0] == 0x539);
    assert(payload_count == 2 && payloads[0] == 0x03020151 && payloads[1] == 4);

    reset(); msg.flags = MIPI_DSI_MSG_REQ_ACK; regs[VID_MODE_CFG / 4] = 0xbf02;
    regs[CMD_MODE_CFG / 4] = CMD_MODE_ALL_LP | 1;
    assert(transfer() == 4 && regs[CMD_MODE_CFG / 4] == 3 && regs[VID_MODE_CFG / 4] == 0x3f02);
    reset(); statuses[0] = default_status; statuses[1] = GEN_CMD_EMPTY;
    statuses[2] = 0; statuses[3] = default_status; status_count = 4;
    assert(transfer() == 4 && status_reads == 4); /* waits for BOTH empty bits */
    reset(); statuses[0] = default_status; status_count = 1; default_status = GEN_CMD_EMPTY;
    assert(transfer() == -ETIMEDOUT && header_count == 1 && status_reads == 23);
    reset(); default_status = GEN_CMD_FULL;
    assert(transfer() == -ETIMEDOUT && !header_count && !payload_count);
    reset(); statuses[0] = default_status; status_count = 1; default_status = GEN_PLD_W_FULL; msg.type = MIPI_DSI_DCS_LONG_WRITE;
    assert(transfer() == -ETIMEDOUT && !header_count && !payload_count);
    reset(); statuses[0] = default_status; statuses[1] = 0; status_count = 2; default_status = GEN_PLD_W_FULL;
    msg.type = MIPI_DSI_DCS_LONG_WRITE; msg.tx_buf = bytes; msg.tx_len = sizeof(bytes);
    assert(transfer() == -ETIMEDOUT && !header_count && payload_count == 1);

    reset(); default_status &= ~GEN_PLD_W_EMPTY;
    assert(transfer() == -ETIMEDOUT && !writes); /* do not append to failed prior payload */
    reset(); dsi.transfer_ready = false;
    assert(transfer() == -EPIPE && !reads && !writes);
    reset(); msg.channel = 4;
    assert(transfer() == -EINVAL && !reads && !writes);
    reset(); msg.tx_len = 1;
    assert(transfer() == -EINVAL && !writes);
    reset(); msg.tx_buf = NULL;
    assert(transfer() == -EINVAL && !writes);
    reset(); msg.tx_len = 0x10000;
    assert(transfer() == -EINVAL && !writes);
    reset(); msg.rx_len = 1;
    assert(transfer() == -EINVAL && !writes);
    reset(); msg.type = MIPI_DSI_GENERIC_LONG_WRITE;
    assert(transfer() == -EOPNOTSUPP && !writes);

    reset(); u8 rx = 0; msg.type = MIPI_DSI_DCS_READ; msg.tx_len = 1;
    msg.rx_buf = &rx; msg.rx_len = 1; reply_on_header = true;
    assert(transfer() == 1 && rx == 0x9c && headers[0] == 0x5106 && !payload_count);
    reset(); msg.type = MIPI_DSI_DCS_READ; msg.tx_len = 1; msg.rx_buf = &rx; msg.rx_len = 3;
    assert(transfer() == -EINVAL && !writes); /* preserve the one-byte read scope */
    reset(); msg.type = MIPI_DSI_DCS_READ; msg.tx_len = 1; msg.rx_buf = &rx; msg.rx_len = 1;
    assert(transfer() == -ETIMEDOUT && header_count == 1);
    reset(); msg.type = MIPI_DSI_DCS_READ; msg.tx_len = 1; msg.rx_buf = &rx; msg.rx_len = 1;
    default_status &= ~GEN_PLD_R_EMPTY;
    assert(transfer() == -EIO && !header_count && reads == 34); /* bounded stale FIFO */

    reset(); pthread_t a, b;
    assert(!pthread_create(&a, NULL, writer, (void *)1));
    assert(!pthread_create(&b, NULL, writer, (void *)2));
    assert(!pthread_join(a, NULL) && !pthread_join(b, NULL));
    assert(header_count == 1000 && payload_count == 2000);
    for (unsigned int i = 0; i < header_count; i++) {
        u8 channel = (headers[i] >> 6) & 3;
        assert(payloads[2*i] == (0x04030200u | channel));
        assert(payloads[2*i+1] == channel);
    }
    assert(!pthread_mutex_destroy(&dsi.transfer_lock));
    assert(!pthread_mutexattr_destroy(&attr));
    printf("PASS: %u host transport cases; real kernel packet builder, mock MMIO, ASan/UBSan; no board claim\n", cases);
    return 0;
}
'''

if __name__ == "__main__":
    main()
