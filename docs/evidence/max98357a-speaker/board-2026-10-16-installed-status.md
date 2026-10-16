# Installed `k230-speaker-test status` on the mainline board, 2026-10-16

Evidence class: on-board command over SSH, running the installed script from a
live-deployed system (not typed by hand). Board clock `2026-10-16T15:28:14Z`.
System `/nix/store/6sh592wyhyca55hwk8ck4n6sgmrl189z-nixos-system-nixos-26.11.20260919.20b1ddd`
(branch `shade-quick-toggles` at `65ee0201`, which includes master `5b36ac00`
with the libgpiod 2 script). Script store path
`/nix/store/r5dczbfn5mkzibgj3p546yjzis50fi5c-k230-speaker-test/bin/k230-speaker-test`.
Kernel `7.3.0-rc5`, libgpiod v2.2.4.

Command: `sudo k230-speaker-test status` — exit 0. Full output:

```
== /proc/asound/cards ==
 0 [K230I2SINNO    ]: K230_I2S_INNO - K230_I2S_INNO
                      K230_I2S_INNO

== aplay -l ==
**** List of PLAYBACK Hardware Devices ****
card 0: K230I2SINNO [K230_I2S_INNO], device 0: Audio 9140e000.inno_codec-0 [Audio 9140e000.inno_codec-0]
  Subdevices: 1/1
  Subdevice #0: subdevice #0

== amixer controls ==
numid=2,iface=MIXER,name='PCM Playback Switch'
numid=1,iface=MIXER,name='PCM Playback Volume'
numid=4,iface=MIXER,name='Mic Capture Switch'
numid=3,iface=MIXER,name='Mic Capture Volume'
numid=5,iface=MIXER,name='External I2S Output Switch'

== External I2S Output Switch ==
numid=5,iface=MIXER,name='External I2S Output Switch'
  ; type=BOOLEAN,access=rw------,values=1
  : values=off

== gpiochip1 line 2 (MAX98357A SDMODE) ==
gpiochip1 2	unnamed         	output

== dmesg (audio-related) ==
[    2.239547] canaan-k230-snd-inno sound: External I2S output disabled by default
[    2.240079] canaan-k230-snd-inno sound: ASoC: CPU DAI (null) not registered
[    2.945812]   #0: K230_I2S_INNO
```

What this shows: every section ran without the 2026-10-01 errors; the route
control exists and reads off; the SDMODE line is visible and not held (no
consumer) while nothing is playing. Limits: no tone was played and nothing was
listened to, so 5.3–5.6 remain open. The `ASoC: CPU DAI (null) not
registered` line is a boot-time probe-deferral message from the kernel and is
recorded, not interpreted.
