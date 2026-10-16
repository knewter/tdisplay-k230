# libgpiod 2 and `amixer -c 0` on the mainline board, 2026-10-16

Evidence class: on-board console commands over SSH, typed by hand (not yet
the installed script). Board clock: `Fri Oct 16 02:56:09 PM UTC 2026`.
Kernel `7.3.0-rc5` (the mainline DRM shell system), libgpiod v2.2.4.

- `/proc/asound/cards` lists `K230I2SINNO`. `amixer -c 0 controls` includes
  `numid=5,iface=MIXER,name='External I2S Output Switch'`, and
  `amixer -c 0 cget` reads `values=off`. The mainline kernel carries the
  route control too.
- `amixer controls` without `-c 0` fails with `Control default open error:
  Host is down`, because the default ALSA device is PipeWire's.
- `gpiodetect` reports `gpiochip1 [9140c000.gpio] (32 lines)`.
- A libgpiod 2 hold, using the exact form the script now uses:

  ```
  gpioset --chip=gpiochip1 --consumer=k230-speaker-test 2=inactive & P=$!
  sleep 0.3; kill -0 $P && echo held        -> held
  gpioinfo -c gpiochip1 2                    -> gpiochip1 2  unnamed  output consumer="k230-speaker-test"
  kill $P; wait $P
  gpioinfo -c gpiochip1 2                    -> gpiochip1 2  unnamed  output
  ```

  The line is requested and held while gpioset runs and released when it is
  killed, which is what `amp_set`/`amp_release` assume. Only `inactive` (amp
  off) was driven; no tone was played.

`nix/k230-speaker-test.nix` now uses these forms. Task 4.2b closes when the
installed `k230-speaker-test status` prints the control and the line
without errors.
