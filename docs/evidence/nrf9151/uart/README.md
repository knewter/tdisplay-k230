# nRF9151 UART3 and enable line (task 2.2, partial)

Evidence class: **board-read**. This was run on the second T-Display K230
board, clipped into the LILYGO keyboard base, on 2026-10-13 at about
19:30 UTC. The commands went over the serial console on `/dev/ttyACM0`
channel 0 while the host held `flock /tmp/k230-board.lock`.

## Setup

- Image: `.#sdImage-landscape` from `master` at `dc2c4dae`.
- Device tree: rebuilt with this branch's `uart3_nrf_pins` and
  `nrf9151_en_pins` (and the keyboard base's I2C4 node from
  `impl/keyboard-base`), with the image's `/chosen/bootargs` copied in. It was
  installed with
  `tools/push-file.py --src <dtb> --dest /boot/k230-tdisplay.dtb --reboot`.

## Observations

- **Console:** channel 0 logged in as root after the reboot.
- **UART:** `dmesg` reported
  `91403000.serial: ttyS3 MMIO32:0x0000000091403000 (irq = 14, base_baud = 3125000) is a 16550A`.
- **Pin muxing,** from `/sys/kernel/debug/pinctrl/*/pinmux-pins`:
  ```
  pin 2 (IO2): device 91403000.serial function nrf9151-en-pins group nrf9151-en-cfg
  pin 28 (IO28): device 91403000.serial function uart3-nrf-pins group uart3-txd-cfg
  pin 29 (IO29): device 91403000.serial function uart3-nrf-pins group uart3-rxd-cfg
  pin 50 (IO50): device 91403000.serial function uart3-nrf-pins group uart3-io50-io51-release-cfg
  pin 51 (IO51): device 91403000.serial function uart3-nrf-pins group uart3-io50-io51-release-cfg
  ```
- **Exchange:** IO2 was held high with
  `setsid nohup timeout 90 gpioset -c gpiochip0 2=1 &`. Then:
  ```
  stty -F /dev/ttyS3 115200 raw -echo
  timeout 12 cat /dev/ttyS3 > /tmp/at.log &   # started 5 s after IO2 high
  printf "AT\r\n" > /dev/ttyS3; sleep 1
  printf "AT+CGMR\r\n" > /dev/ttyS3; sleep 1
  printf "AT+CFUN?\r\n" > /dev/ttyS3
  ```
  `cat -v /tmp/at.log` gave:
  ```
  OK^M
  ^M
  mfw_nrf91x1_2.0.3^M
  ^M
  OK^M
  ^M
  +CFUN: 1^M
  ^M
  OK^M
  ```

The modem firmware is `mfw_nrf91x1_2.0.3`. `+CFUN: 1` means the base's
application firmware had already set the modem fully functional on its own
within about 7 s of power-on, with no command from us.

## Limits

- **The task's terminal tool was not used.** `cat` and `printf` replaced
  `microcom`.
- **Channel 1 silence was not checked,** so task 2.2 stays open.
- **IO2 power-up was not isolated.** IO2 had not been driven before the
  `gpioset`, and it was not shown that the modem is unpowered while IO2 is
  low. The modem could also have been powered by the base's own battery.
- **No identifier was queried.** IMEI, ICCID and IMSI were not requested.
