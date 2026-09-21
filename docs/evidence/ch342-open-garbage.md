# The garbage burst when we open /dev/ttyACM0

Investigated 2026-09-21 on `solomon` (Manjaro, Linux 7.1.9-1-MANJARO, in-tree
`cdc_acm`, pyserial 3.5, Python 3.14.7) against the LilyGO T-Display-K230's
CH342K console bridge (`1a86:55d2`, two CDC-ACM ports: `ttyACM0` = UART0,
`ttyACM1` = UART3).

**The board was never corrupted. Every burst we chased was made on this host.**

## 1. The short version

`ModemManager` is running on this machine and probes `/dev/ttyACM0` and
`/dev/ttyACM1` every single time the CH342 enumerates — which, because the
board resets constantly during debugging, is every single time we go to
capture a boot. During the probe it:

- takes the port with `TIOCEXCL`, so our own `open()` is refused for the
  duration;
- reprograms the CH342's UART to **57600 baud** — its default — while the
  K230 is talking at 115200;
- pulses the line at **baud 0** ("flashing" the port);
- writes **`AT`** six times, three seconds apart — an **18-second** window;
- then writes a binary **QCDM/DIAG** frame;
- gives up ("unhandled port type") and releases the port.

That single cause produces both symptoms we saw:

- **RX garbage.** For 18+ seconds the CH342 samples a 115200 line at 57600.
  The mis-framed bytes accumulate in the chip's internal receive FIFO. When we
  finally open the port and pyserial sets 115200, the FIFO drains *first* —
  garbage, then perfectly clean text. A periodic source (an idle prompt, a
  repeated line) undersampled 2:1 produces a short repeating byte pattern,
  which is exactly the shape of the `0xF4 0xA4 0xF4 0xA4 …` burst; it is not
  noise.
- **TX garbage into U-Boot.** ModemManager's `AT` bytes are transmitted at
  57600 into a receiver running at 115200. U-Boot decodes them as junk
  characters, keeps the printable ones in its command-line buffer, and echoes
  them back at us. That is where `Unknown command 'kKBBBBkBBBkrun'` comes
  from: the junk was already sitting in U-Boot's line editor before we sent
  `run`, and what we "captured" was U-Boot's echo of it.

There is a second, smaller contributor that survives even if ModemManager is
removed: `cdc_acm` programs **9600 baud** into every CDC device at probe time
and does not touch it again until the first `open()`. So the very first open
after each enumeration always has some mis-sampled data behind it.

## 2. Evidence

### 2.1 ModemManager is probing this exact device (primary, this host)

`journalctl -u ModemManager` on `solomon`, unedited:

```
Sep 21 11:32:33  <msg> [ttyACM0/probe] probe step: start
Sep 21 11:32:33  <msg> [ttyACM0/probe] probe step: AT open port
Sep 21 11:32:33  <msg> [ttyACM0/probe] probe step: AT
Sep 21 11:32:51  <msg> [ttyACM0/probe] probe step: AT close port
Sep 21 11:32:51  <msg> [ttyACM0/probe] probe step: QCDM
Sep 21 11:32:51  <msg> [ttyACM0/probe] probe step: done
Sep 21 11:32:51  <msg> [device …/usb3/3-1] creating modem with plugin 'generic' and '2' ports (1a86:55d2)
Sep 21 11:32:51  <wrn> [plugin/generic] could not grab port ttyACM0: Cannot add port 'tty/ttyACM0', unhandled port type
```

The same block repeats at 11:06:22, 11:32:33 and 11:39:58 — once per
re-enumeration. Note the vendor/product: `(1a86:55d2)`, our CH342. Note the
duration: **18 seconds**, `11:32:33` → `11:32:51`.

It happens because `/usr/lib/udev/rules.d/80-mm-candidate.rules` says, with no
vendor filtering at all:

```
SUBSYSTEM=="tty", ENV{ID_MM_CANDIDATE}="1"
```

and `ModemManager.service` on this host starts with a bare
`ExecStart=/usr/bin/ModemManager` — no `--filter-policy=strict`.

### 2.2 What ModemManager does to the port (primary, MM 1.24.2 source)

Installed version is 1.24.2 (`mmcli --version`), so these quotes are from
`modemmanager 1.24.2-2` on sources.debian.org — the matching release.

`src/mm-port-serial.c`:

```c
g_param_spec_uint (MM_PORT_SERIAL_BAUD, "Baud", "Baud rate",
                   0, G_MAXUINT, 57600, G_PARAM_READWRITE)
```

→ **57600 is the default baud** when nothing sets `ID_MM_TTY_BAUDRATE`
(nothing does here). Corroborated by a string in the shipped binary:

```
$ strings -a /usr/bin/ModemManager | grep 57600
baudrate invalid: %u; defaulting to 57600
```

Same file:

```c
if (ioctl (self->priv->fd, TIOCEXCL) < 0)     /* exclusive access */
…
tcflush (self->priv->fd, TCIOFLUSH);          /* on open and on close */
…
stbuf.c_cflag |= (bits | parity | stopbits | CLOCAL | CREAD);
```

and `mm_port_serial_flash()` drops the port to **`B0`** for `flash_time` and
then restores the speed. The binary carries the matching help text:

```
$ strings -a /usr/bin/ModemManager | grep -i flash
Flashing the port (0 baud for a short period) is allowed.
```

`src/mm-port-probe.c`:

```c
static const MMPortProbeAtCommand at_probing[] = {
    { "AT",  3, mm_port_probe_response_processor_is_at },
    …
};
```

six tries by default at a 3 s timeout each = the 18 s the journal shows, then
a QCDM version-info frame (`0x7E`-delimited HDLC). The binary also contains
`ATE1`, `+GCAP`, `+CGMI`, `+CGMM` for the follow-up probes.

`TIOCEXCL` is why `capture-boot.py`'s `except: time.sleep(0.2)` retry loop
exists at all, and why the comment there — "udev has not finished with it yet"
— is wrong. It is not udev. It is ModemManager holding the port for 18 seconds
while writing `AT` at the wrong baud into U-Boot.

### 2.3 What cdc_acm does on probe and on open (primary, kernel source)

From `drivers/usb/class/cdc-acm.c` (mainline):

```c
	/* in acm_probe() */
	acm->line.dwDTERate = cpu_to_le32(9600);
	acm->line.bDataBits = 8;
	acm_set_line(acm, &acm->line);
```

```c
	acm_tty_driver->init_termios.c_cflag = B9600 | CS8 | CREAD |
							HUPCL | CLOCAL;
```

```c
static int acm_port_activate(struct tty_port *port, struct tty_struct *tty)
{
	…
	acm_tty_set_termios(tty, NULL);     /* SET_LINE_CODING */
	clear_bit(ACM_THROTTLED, &acm->flags);
	retval = acm_submit_read_urbs(acm, GFP_KERNEL);   /* only now */
```

So: **the chip is programmed to 9600 the moment it enumerates, and stays
there until somebody opens the tty.** Read URBs are only submitted at open,
which means that until then nothing drains the chip's bulk IN endpoint and
whatever the chip decoded piles up in its own FIFO.

Two further details from the same file that matter:

```c
	if (C_BAUD(tty) == B0) {
		newline.dwDTERate = acm->line.dwDTERate;
		newctrl &= ~USB_CDC_CTRL_DTR;
	}
```

— this is what ModemManager's "flash" hits: `B0` makes `cdc_acm` drop DTR.

```c
	{ USB_DEVICE(0x1a86, 0x55d3), .driver_info = MISSING_CAP_BRK, },
```

— WCH's CH343 (`55d3`) is already quirked in-tree for lying about BREAK
support. Our `55d2` is not in the table. Mentioned only to show that WCH CDC
parts are known to need special handling; it is **not** the cause here.

### 2.4 What pyserial does on open (primary, installed source)

`/usr/lib/python3.14/site-packages/serial/serialposix.py`, `Serial.open()`, in
order:

1. `os.open(port, O_RDWR|O_NOCTTY|O_NONBLOCK)` — **this is where the kernel
   runs `acm_port_activate` and starts reading at whatever baud is currently
   programmed**, and where `tty_port_block_til_ready()` raises DTR/RTS;
2. `self._reconfigure_port(force_update=True)` — the `tcsetattr` that finally
   sends `SET_LINE_CODING` for 115200;
3. `_update_dtr_state()` / `_update_rts_state()`;
4. `self._reset_input_buffer()` → `termios.tcflush(fd, TCIFLUSH)`.

Three consequences, all load-bearing:

- **pyserial already flushes input on open, and it does not help.** `tcflush`
  discards what has reached the tty buffer at that instant. The chip's FIFO
  and the in-flight bulk IN URBs are downstream of it and arrive afterwards.
  This is precisely why "it already calls `reset_input_buffer()`" has not
  saved us — the flush is simply too early.
- **You cannot hold DTR/RTS low across `open()`.** The kernel raises them in
  step 1; pyserial's `.dtr = False` is applied in step 3, after the fact. The
  `dtr`/`rts` setters only call the ioctl `if self.is_open`, so setting them
  before open just records the wish. `dsrdtr=True` / `rtscts=True` merely make
  pyserial *skip* its own ioctl in step 3 — they do not stop the kernel.
- **`exclusive=True` is `flock()`, not `TIOCEXCL`:**
  `fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)`. It is advisory. It
  will keep a second copy of our script (or `tio`, which also uses flock) out,
  but it cannot keep ModemManager out — ModemManager does not take an flock,
  it takes `TIOCEXCL`, and `TIOCEXCL` beats us, not the other way round.

The kernel-side DTR/RTS raise is `tty_port_block_til_ready()` →
`tty_port_raise_dtr_rts()` → `acm_port_dtr_rts(port, true)` → CDC
`SET_CONTROL_LINE_STATE` with DTR|RTS. It is unconditional; there is no
userspace opt-out short of patching the kernel.
(<https://qsantos.fr/2025/05/03/linux-always-toggles-dtr-rts/>)

### 2.5 DTR/RTS are a dead end on this board (primary, the schematic)

`repo/schematic/T-Display K230_V1.0_NEW.pdf`, U11, is a **CH342K** — the
10-pin part. Its entire net list on this board is:

```
UD+ , UD- , GND , VDD5 , VIO , V3 ,
TXD0_CH342 -> UART0_RXD      RXD0_CH342 <- UART0_TXD
TXD1_CH342 -> UART3_RXD      RXD1_CH342 <- UART3_TXD
```

**There is no DTR, RTS, CTS, DSR, DCD or RI pin on the package, and none on
the board.** Nothing the host does to modem control lines can physically
reach the K230. Every hardware theory that routed through DTR — auto-reset,
boot-strapping, a BREAK on the target — is ruled out by the schematic. The
garbage is data, and only data.

### 2.6 A wrong-baud receiver reproduces the *shape* of what we saw

Written for this investigation (kept out of the repo; it touches no
hardware): build the physical 8N1 waveform for a byte stream at one baud, then
sample it the way a UART receiver at another baud would — hunt for a start
bit, sample eight data bits at the mid-point, resynchronise.

ModemManager writing `AT\r` at 57600 into a 115200 receiver:

```
TX=57600 RX=115200
  raw: 06 90 60 66 1e 98 00 06 66 e6 80 06 98 60 66 1e 98 00 06 66 e6 80 …
  the printable subset U-Boot's line editor would keep and echo: b'`ff`ff`ff'
```

An idle `K230# ` prompt at 115200 sampled by a receiver at 57600:

```
TX=115200 RX=57600
  raw: 94 48 c8 5a 1a 98 5a 1a 68 5a 1a 98 5a 1a 98 5a 1a 98 5a 1a 98 …
```

Both reproduce the two things that made the real bursts look like hardware
faults: they are **short, repeating, low-entropy patterns**, and the
host→board direction yields a run of ordinary printable ASCII, because U-Boot
throws away the non-printables and keeps and echoes the rest.

This is a *shape* match, not a byte-for-byte reconstruction of
`kKBBBBkBBBk` / `0xF4 0xA4` — we do not know exactly what the board was
printing at that instant, nor which of the two wrong-baud epochs (9600 from
`cdc_acm` probe, 57600 from ModemManager) each burst came from. **Treat the
exact byte mapping as unverified; treat the mechanism as established.**

## 3. What was considered and ruled out

| Hypothesis | Verdict |
|---|---|
| Opening asserts DTR/RTS and the CH342 answers with data or a BREAK | **Ruled out.** CH342K has no DTR/RTS pins (§2.5). The kernel does raise the CDC control-line bits, but they go nowhere. |
| `HUPCL` on close causes a transition on the next open | **Not the cause.** `cdc_acm`'s `init_termios` does carry `HUPCL`, and the hangup does drop DTR — but with no DTR pin it cannot reach the board. `stty -hupcl` is not worth doing here. |
| The chip is reprogrammed after open, so in-flight bytes decode at the wrong rate | **Confirmed, and it is the core of it** (§2.3, §2.4) — but the window is far wider than "in flight": it is the whole interval from enumeration to our `tcsetattr`, which ModemManager stretches to 18+ seconds. |
| `reset_input_buffer()` at open fixes it | **No.** pyserial already does exactly that and it fires too early (§2.4). It works only *after* a settle delay. |
| `exclusive=True` fixes it | **No.** It is an advisory `flock`, and ModemManager uses `TIOCEXCL` (§2.4). Still worth having to stop two copies of our own tooling fighting. |
| Swap `cdc_acm` for WCH's vendor driver | **Helps a little, does not fix it.** `WCHSoftGroup/ch343ser_linux` covers CH342 and sets `ch343->line.dwDTERate = 115200` at probe rather than 9600, so it removes the `cdc_acm` 9600 epoch. But its device is still a `tty`, so `80-mm-candidate.rules` still tags it and ModemManager still probes it (§2.1). An out-of-tree module to rebuild on every kernel bump, for part of the problem. Not recommended. |
| A WCH errata / CH342 firmware bug | **No evidence found, and none needed** — the host-side explanation is complete and each step is observable in the journal. |
| The board is crashing | **No.** This is the thing that cost us the most time. |

## 4. The fix

### 4.1 Prevention: stop ModemManager touching the board (do this first)

`tools/99-tdisplay-k230-no-modemmanager.rules`, installed to
`/etc/udev/rules.d/`:

```
SUBSYSTEM=="usb", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="55d2", ENV{ID_MM_DEVICE_IGNORE}="1"
```

```
sudo install -m0644 tools/99-tdisplay-k230-no-modemmanager.rules /etc/udev/rules.d/
sudo udevadm control --reload
# then unplug and replug the console cable
```

`ID_MM_DEVICE_IGNORE` is honoured under every filter policy including strict,
and tagging the **usb_device** (not the tty) covers both ports at once.
(<https://modemmanager.org/docs/modemmanager/port-and-device-detection/>)

This removes the 18-second `TIOCEXCL` lockout, the `AT` bytes going into
U-Boot, the `B0` flash, and the 57600 epoch. It does **not** remove the
`cdc_acm` 9600-at-probe epoch, so keep §4.2 as well.

`systemctl mask ModemManager` would also work and is the right move on a
machine with no WWAN hardware, but the udev rule is narrower and survives
reinstalls.

### 4.2 Mitigation in `tools/capture-boot.py`

Complete prevention is not available: even with ModemManager gone, `cdc_acm`
leaves the chip at 9600 from enumeration until the first open, so the first
open always has *some* mis-sampled data queued behind it. The script therefore
has to discard deterministically rather than hope. It now:

- waits `--settle` seconds (default 0.30) after opening before doing anything
  else, then calls `reset_input_buffer()` / `reset_output_buffer()`;
- does not throw the settle-window bytes away silently — it writes them to the
  log inside an explicit `--- discarded N bytes … ---` marker, so a future
  reader can never again mistake them for the board misbehaving;
- clears the `--expect` match buffer at that point, so a prompt can only ever
  be matched in *post-flush* data and `--send` can never fire off garbage;
- sends `\x15` (kill-line: `CTL_CH('u')` in U-Boot's `cread_line`, `VKILL` in
  a canonical tty) immediately before each `--send`, so anything already
  sitting in the target's line editor is discarded instead of being prefixed
  onto our command. `--no-line-kill` turns this off;
- takes an advisory `flock` (`--no-exclusive` to opt out) and says so in the
  log when the port is busy, instead of retrying in silence;
- checks at startup whether ModemManager is running without the udev rule in
  place, and prints the one-line fix.

`--hammer`, `--kick`, `--expect`/`--send`, `--out`, `--seconds`, `--append`
and `--quiet-exit` are unchanged. `--hammer` and `--kick` now run *after* the
settle+flush, which costs 0.3 s of the autoboot window and in exchange stops
the hammer's own keystrokes from being mixed into the discarded region. With
the udev rule installed, `--settle 0.05` is enough.

## 5. Confidence

**Established from primary sources:**

- ModemManager probes `1a86:55d2` on this host for 18 s per enumeration, holds
  it with `TIOCEXCL`, uses 57600, flashes at `B0`, writes `AT` and a QCDM
  frame (journal from this machine + MM 1.24.2 source + strings in the
  installed binary).
- `cdc_acm` programs 9600 at probe, sets line coding before submitting read
  URBs at open, and has `HUPCL` in `init_termios` (mainline source).
- pyserial's open order, the too-early `tcflush`, `exclusive` being `flock`,
  and DTR/RTS being applied only after open (installed 3.5 source).
- The kernel raises DTR/RTS unconditionally on open and there is no userspace
  opt-out.
- The CH342K on this board has no modem-control pins (the schematic in-tree).
- WCH's `ch343ser_linux` sets 115200 at probe instead of 9600.

**Inference, consistent with everything above but not directly measured:**

- That each specific burst we saw (`kKBBBBkBBBk`, `0xF4 0xA4 …`) is
  byte-for-byte the product of one particular wrong-baud epoch. The shape is
  reproduced by simulation; the exact bytes are not, because the board's
  output at that instant is unknown.
- That `kKBBBBkBBBk` reaching U-Boot's command buffer is specifically
  ModemManager's `AT` traffic rather than the tail of some other write. It is
  the only writer on the port at that time and it writes at the wrong baud, so
  it is the strong candidate — but we did not capture it with a bus analyser.
- That the CH342's receive FIFO, rather than an in-flight URB, is where the
  mis-decoded bytes wait. WCH documents "independent transmit-receive buffers"
  but the datasheet PDF would not render for a size figure.

**The one way to close both inferences** — once the board is free — is to
install the udev rule, replug, and capture with `--settle 0`. If the burst
disappears entirely, ModemManager was the whole story; if a short burst
remains, that residue is the `cdc_acm` 9600 epoch. Neither test may be run
while a capture is live.

## Sources

- `journalctl -u ModemManager` on `solomon`, 2026-09-21 (this host)
- `strings -a /usr/bin/ModemManager`, `mmcli --version` → 1.24.2 (this host)
- `/usr/lib/udev/rules.d/80-mm-candidate.rules`,
  `/usr/lib/systemd/system/ModemManager.service` (this host)
- `/usr/lib/python3.14/site-packages/serial/serialposix.py` (pyserial 3.5, this host)
- `repo/schematic/T-Display K230_V1.0_NEW.pdf` (in-tree)
- [`drivers/usb/class/cdc-acm.c`](https://github.com/torvalds/linux/blob/master/drivers/usb/class/cdc-acm.c)
- [ModemManager 1.24.2 `src/mm-port-serial.c`](https://sources.debian.org/src/modemmanager/1.24.2-2/src/mm-port-serial.c/)
- [ModemManager 1.24.2 `src/mm-port-probe.c`](https://sources.debian.org/src/modemmanager/1.24.2-2/src/mm-port-probe.c/)
- [ModemManager: port and device detection](https://modemmanager.org/docs/modemmanager/port-and-device-detection/)
- [ModemManager: modem filter](https://www.freedesktop.org/software/ModemManager/api/latest/ref-overview-modem-filter.html)
- [Downtown Doug Brown, "Fix for USB serial port being opened by ModemManager at startup"](https://www.downtowndougbrown.com/2016/10/fix-for-usb-serial-port-being-opened-by-modemmanager-at-startup/)
- [Quentin Santos, "Linux always toggles DTR & RTS"](https://qsantos.fr/2025/05/03/linux-always-toggles-dtr-rts/)
- [`WCHSoftGroup/ch343ser_linux`](https://github.com/WCHSoftGroup/ch343ser_linux)
- [CH342 datasheet (v1E)](https://docs.sparkfun.com/SparkFun_RTK_Postcard/assets/component_documentation/CH342%20Datasheet.pdf)
