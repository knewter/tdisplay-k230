#!/usr/bin/env bash
# Read-only probe of the LILYGO keyboard base (openspec/changes/
# the-keyboard-base-types-lights-and-reports-its-battery, task 1.1).
#
# Run on the board as root, holding the board lock on the host:
#   flock /tmp/k230-board.lock ... 'bash keyboard-base-probe.sh'
#
# It writes nothing to the base. Every I2C access is an i2cget read; the
# script refuses to run if any I2C write command appears in it. Pin state is
# read from pinctrl and gpio debugfs, which never request a line: requesting
# IO43 (the keypad's active-low reset) as an input could let it float.
#
# Registers deliberately not read:
#   BQ25896 0x0C  fault register; reading it clears latched faults.
#   TCA8418 0x04  key event FIFO; reading it pops an event.
set -u

w1=i2c; w2=set; w3=transfer
if grep -qE "${w1}(${w2}|${w3})" "$0"; then
	echo "refusing: this probe must contain no I2C write command" >&2
	exit 2
fi

echo "# keyboard-base-probe $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "# kernel $(uname -r)"

dbg=/sys/kernel/debug
mountpoint -q "$dbg" || mount -t debugfs debugfs "$dbg"
modprobe i2c-dev 2>/dev/null

echo
echo "## pin muxing (pinctrl debugfs)"
for pin in 2 28 29 42 43 46 47 50 51 52; do
	grep -h "^pin $pin (IO$pin)" "$dbg"/pinctrl/*/pinmux-pins
done

echo
echo "## GPIO state (IO42 = gpio1 10, IO43 = gpio1 11, IO52 = gpio1 20)"
grep -hE "gpio-(42|43|46|47|52) " "$dbg"/gpio || echo "(no requested line among IO42/43/46/47/52)"
# gpioinfo does not request a line. A line is sampled only when it is
# already an input, so gpioget's input request reconfigures nothing.
for off in 10 11 20; do
	info=$(gpioinfo -c gpiochip1 "$off")
	echo "$info"
	case "$info" in
	*input*) echo "gpiochip1 $off level: $(gpioget -c gpiochip1 --numeric "$off")" ;;
	*) echo "gpiochip1 $off not an input; level not sampled" ;;
	esac
done

bus=$(ls -d /sys/bus/platform/devices/91409000.i2c/i2c-* 2>/dev/null | head -1)
bus=${bus##*/i2c-}
if [ -z "$bus" ]; then
	echo "no i2c adapter on 91409000.i2c; is i2c4 enabled in the DTB?" >&2
	exit 1
fi

echo
echo "## i2cdetect -y -r $bus (hardware I2C4, IO46 SCL / IO47 SDA)"
i2cdetect -y -r "$bus"

present() { i2cget -y "$bus" "$1" >/dev/null 2>&1 || i2cget -y "$bus" "$1" 0x00 >/dev/null 2>&1; }

rb() { # addr reg...
	local a=$1; shift
	for r in "$@"; do
		printf '%s reg 0x%02x = %s\n' "$a" "$r" "$(i2cget -y "$bus" "$a" "$r" b 2>&1)"
	done
}

rw() { # addr reg... (little-endian words)
	local a=$1; shift
	for r in "$@"; do
		printf '%s cmd 0x%02x = %s\n' "$a" "$r" "$(i2cget -y "$bus" "$a" "$r" w 2>&1)"
	done
}

echo
echo "## BQ25896 charger 0x6b, registers 0x00-0x14 except 0x0c"
rb 0x6b 0x00 0x01 0x02 0x03 0x04 0x05 0x06 0x07 0x08 0x09 0x0a 0x0b \
	0x0d 0x0e 0x0f 0x10 0x11 0x12 0x13 0x14

echo
echo "## BQ27220 gauge 0x55, standard commands 0x06-0x3c (words)"
rw 0x55 0x06 0x08 0x0a 0x0c 0x0e 0x10 0x12 0x14 0x16 0x18 0x1a 0x1c 0x1e \
	0x20 0x22 0x24 0x26 0x28 0x2a 0x2c 0x2e 0x30 0x32 0x34 0x36 0x38 0x3a 0x3c

echo
echo "## TCA8418 keypad 0x34: CFG 0x01, INT_STAT 0x02, KEY_LCK_EC 0x03"
rb 0x34 0x01 0x02 0x03

echo
echo "## XL9555 expander 0x20: input 0-1, output 2-3, polarity 4-5, config 6-7"
rb 0x20 0x00 0x01 0x02 0x03 0x04 0x05 0x06 0x07

echo
echo "## DRV2605 haptics 0x5a"
if present 0x5a; then
	rb 0x5a 0x00
else
	echo "0x5a does not answer: DRV2605 not fitted"
fi

echo
echo "## other answering addresses"
echo "0x38 is expected to be the AHT20 humidity sensor (not read)"
echo "# end"
