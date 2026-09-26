# A tiny operator helper for the two audio output routes this board has:
# the always-present Inno codec (headphone/line-out) and the optional
# MAX98357A external I2S amplifier, gated by GPIO34 and the
# "External I2S Output Switch" ALSA control added by
# nix/patches/canaan-audio-external-i2s-switch.patch.
#
# Deliberately shells out to `amixer`/`speaker-test` and the libgpiod v2
# CLI rather than talking to /dev/snd or /dev/gpiochip* directly: every
# command here is exactly one a human operator can also type over the
# console by hand, which is the point -- see the board test plan in
# docs/evidence/max98357a-speaker.md.
#
# UNVERIFIED: the `gpioset --mode=signal ... &` / `kill` pairing assumes
# libgpiod v2 CLI semantics (request the line, hold it until signaled,
# release on exit). This has not been run on the board. If the installed
# gpioset rejects --mode=signal, run `gpioset --help` on the board and
# adjust; the fallback note is printed by this script's own error path.
{ writeShellScriptBin, alsa-utils, libgpiod }:

writeShellScriptBin "k230-speaker-test" ''
  set -u

  AMIXER=${alsa-utils}/bin/amixer
  APLAY=${alsa-utils}/bin/aplay
  SPEAKER_TEST=${alsa-utils}/bin/speaker-test
  GPIOSET=${libgpiod}/bin/gpioset
  GPIOGET=${libgpiod}/bin/gpioget
  GPIOINFO=${libgpiod}/bin/gpioinfo
  GPIODETECT=${libgpiod}/bin/gpiodetect

  # MAX98357A shutdown/enable line. HARDWARE_PINMAP.md (Xinyuan-LilyGO/
  # T-Display-K230, k230_bsp/docs/HARDWARE_PINMAP.md) and
  # ui_hardware.c:68 (AMP_SHUTDOWN_GPIO 34) agree: GPIO34, plain GPIO, high
  # enables the amp. GPIO34 falls in the SoC's second 32-pin bank
  # (gpio1_ports covers 32-63, k230.dtsi:415-421), offset 34-32=2.
  AMP_CHIP="gpiochip1"
  AMP_OFFSET=2
  ROUTE_CONTROL="External I2S Output Switch"

  AMP_HOLD_PID=""

  cleanup() {
    if [ -n "$AMP_HOLD_PID" ]; then
      kill "$AMP_HOLD_PID" 2>/dev/null
      wait "$AMP_HOLD_PID" 2>/dev/null
    fi
  }
  trap cleanup EXIT

  usage() {
    echo "usage: k230-speaker-test <status|internal|external> [alsa-device]" >&2
  }

  amp_set() {
    # $1 = active|inactive
    "$GPIOSET" --mode=signal --chip="$AMP_CHIP" "$AMP_OFFSET=$1" &
    AMP_HOLD_PID=$!
    # Give the request a moment to land before anything depends on it.
    sleep 0.2
    if ! kill -0 "$AMP_HOLD_PID" 2>/dev/null; then
      echo "k230-speaker-test: gpioset exited immediately; the line may" >&2
      echo "  already be busy, or this libgpiod build may not accept" >&2
      echo "  --mode=signal. Run 'gpioset --help' on the board and compare." >&2
      AMP_HOLD_PID=""
      return 1
    fi
    return 0
  }

  amp_release() {
    if [ -n "$AMP_HOLD_PID" ]; then
      kill "$AMP_HOLD_PID" 2>/dev/null
      wait "$AMP_HOLD_PID" 2>/dev/null
      AMP_HOLD_PID=""
    fi
  }

  route_set() {
    # $1 = 0|1. Absent on an unpatched kernel -- report rather than fail
    # silently, since that is exactly the "DT/kernel change not installed
    # to /boot yet" failure mode.
    if ! "$AMIXER" -q cset name="$ROUTE_CONTROL" "$1" 2>/dev/null; then
      echo "k230-speaker-test: no '$ROUTE_CONTROL' ALSA control." >&2
      echo "  This means the running kernel does not carry" >&2
      echo "  canaan-audio-external-i2s-switch.patch yet -- a DT/kernel" >&2
      echo "  change needs a /boot install (Image + dtb) and a reboot; it" >&2
      echo "  does not take effect from a plain system activation." >&2
      return 1
    fi
    return 0
  }

  cmd_status() {
    echo "== /proc/asound/cards =="
    cat /proc/asound/cards 2>&1 || echo "(no /proc/asound/cards -- no sound card bound)"
    echo
    echo "== aplay -l =="
    "$APLAY" -l 2>&1
    echo
    echo "== amixer controls =="
    "$AMIXER" controls 2>&1
    echo
    echo "== $AMP_CHIP line $AMP_OFFSET (MAX98357A SDMODE) =="
    "$GPIODETECT" 2>&1 | grep -q "$AMP_CHIP" \
      && "$GPIOINFO" "$AMP_CHIP" 2>&1 | sed -n "1p;$((AMP_OFFSET + 2))p" \
      || echo "$AMP_CHIP not found by gpiodetect"
    echo
    echo "== dmesg (audio-related) =="
    dmesg 2>&1 | grep -iE 'max98357|i2s|inno|asoc|canaan.*audio' || echo "(no matching dmesg lines)"
  }

  cmd_internal() {
    device="''${1:-default}"
    route_set 0
    amp_set inactive || true
    echo "Playing 440 Hz sine through the Inno codec route (headphone/line-out, device=$device)."
    "$SPEAKER_TEST" -D "$device" -c1 -t sine -f 440 -l1
  }

  cmd_external() {
    device="''${1:-default}"
    if ! route_set 1; then
      exit 1
    fi
    if ! amp_set active; then
      route_set 0
      exit 1
    fi
    echo "MAX98357A SDMODE driven high; playing 440 Hz sine (device=$device)."
    "$SPEAKER_TEST" -D "$device" -c1 -t sine -f 440 -l1
    status=$?
    amp_release
    route_set 0
    exit $status
  }

  case "''${1:-}" in
    status) cmd_status ;;
    internal) cmd_internal "''${2:-}" ;;
    external) cmd_external "''${2:-}" ;;
    *) usage; exit 64 ;;
  esac
''
