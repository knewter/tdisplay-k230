# `wpctl`/`pw-dump`/`pw-cli`: what was checked, and where

Change: `the-handheld-controls-volume`. Checked 2026-09-27 against a real,
running PipeWire 1.6.8 / WirePlumber session **on a development host, not
this board** -- this board has no PipeWire session yet
(`grep -rn pipewire nix/` before this change finds only `nix/video-probe.
nix`'s `pipewireSupport = false` for mpv's own build). Everything below
grounds the parser's object schema, the cubic-curve claim, and the
persistent-process command shapes this change relies on; it does not stand
in for a board capture. `docs/evidence/volume/` (task 7.1's QEMU capture)
and a future `docs/evidence/volume/board/` are the board/QEMU evidence
classes; this file is the "checked against a real PipeWire, not guessed"
class, the same role `docs/evidence/max98357a-speaker.md` plays for the
kernel source it reads.

## The cubic curve: `wpctl set-volume` already applies it

```
$ wpctl get-volume 39
Volume: 0.58
$ wpctl set-volume 39 0.58   # sets the sink directly to this linear-looking value
$ pw-dump 39 | jq '.[0].info.params.Props[0] | {volume, channelVolumes, mute}'
{
  "volume": 1.0,
  "channelVolumes": [0.195114, 0.195114],
  "mute": false
}
```

`0.58 ** 3 = 0.195112`, matching the captured `channelVolumes` to 5 decimal
places. A second, independent data point from the same session (a
different sink, set by `wpctl set-volume 39 0.57` in an earlier step):
`channelVolumes: [0.185114... ]` observed as `0.185193` predicted from
`0.57 ** 3`; `wpctl status` had separately shown that sink's own displayed
volume as `[vol: 0.57]`. `wpctl`'s own `VOL[%]` argument to `set-volume`
is therefore already the cubic-perceptual value, not a raw linear gain --
`volume::percent_to_linear`/`linear_to_percent` in this change reproduce
that same curve for the shell's own throttled live-drag writes, which
bypass `wpctl` for cost reasons (`design.md` Decision 2) and so must
compute it themselves rather than relying on `wpctl` to.

`wpctl set-volume ID <percent>%` (no `+`/`-` suffix) sets the sink to that
absolute percent, confirmed directly:

```
$ wpctl set-volume 39 42%
$ wpctl get-volume 39
Volume: 0.42
$ wpctl set-volume 39 57%
$ wpctl get-volume 39
Volume: 0.57
```

`wpctl set-mute ID 1|0|toggle` and `wpctl get-volume ID` reporting
`Volume: 0.58 [MUTED]` were both confirmed the same way.

## `pw-dump --monitor`'s framing: one full dump, then deltas only

A 3-second idle capture (`timeout 3 pw-dump --monitor`) on a live desktop
session, with nothing changing, produced **exactly one** top-level JSON
array (128 objects, matching a plain one-shot `pw-dump`'s own object
count) -- confirming `--monitor` does not re-print the full graph on a
timer. A second capture, with a `wpctl set-volume` and two `wpctl
set-mute` calls run partway through, produced **8** top-level JSON values
total: the initial 128-object array, then seven small arrays of 1-2
objects each -- never a full 128-object re-dump. One of those was directly
the sink's own volume change (a 2-object array: the changed sink plus an
unrelated USB audio device renegotiation event that happened to land in
the same PipeWire core iteration); the others were `wpctl`'s own transient
client connect/disconnect (each `wpctl` invocation is itself a short-lived
PipeWire client). This is why `pipewire_ipc::Accumulator` keeps one
running graph across the monitor child's whole life rather than treating
each array as a complete snapshot -- an earlier draft of this parser did
the latter and silently dropped every sink/stream a given change did not
itself touch.

Object removal's shape, captured directly from one of `wpctl`'s own
transient-client disconnect events:

```json
[
  { "id": 103, "info": null }
]
```

An object's `info` going `null` is the removal signal; an object simply
absent from a given array means "unchanged," never "removed."

## `pw-cli`'s persistent stdin mode needs its own registry sync first

Piping several commands into a fresh `pw-cli` process's stdin all at once
(`printf 'ls Node\ni 39\nq\n' | pw-cli`) fails every command against a
real, existing global id (`Error: "i: unknown global '39'"`), even though
`pw-cli ls Node` as a one-shot **CLI-argument** invocation
(`pw-cli ls Node`) lists that same id immediately. Holding the same
`pw-cli` process open (a FIFO feeding its stdin) and waiting about a
second after connecting before sending `i 39` succeeds and returns the
node's full info; a `set-param 39 Props '{ "channelVolumes": [ 0.33, 0.33
] }'` sent the same way immediately afterward took effect, confirmed via a
fresh `pw-dump 39` showing `channelVolumes: [0.33, 0.33]`
(`wpctl get-volume 39` did *not* pick up this particular change --
`wpctl`'s own cached view is evidently mediated through WirePlumber's
mixer state rather than a raw node-Props read, and a raw external
`set-param` does not update that cache; `pw-dump`'s own view, which is
what this shell's graph watcher reads, updated correctly and immediately).
The one-shot CLI-argument form of `pw-cli` waits out this same registry
sync internally before running its single command, which is why it did
not show the same failure. This only matters once, at this shell's own
persistent `pw-cli` writer's startup -- by the time a person's first drag
is physically possible the writer has been alive far longer than the
roughly one-second sync window observed here.

## What this does *not* establish

Every capture above is from a development host's own PipeWire session --
a real Arctis Nova Pro Wireless USB headset and a few desktop ALSA
devices, not this board's Inno codec or (if present) an external I2S
route. Whether this board's own WirePlumber names its Inno sink or any
external-I2S route the way `tests/fixtures/pipewire/*.json` assume
(`alsa_output.platform-canaan_k230_audio.k230-i2s-{inno,external}`) is
UNVERIFIED and is task 3.3's own open board task. The object *schema*
(`media.class`, `node.name`, `node.description`, `application.name`,
`application.icon-name`, `Props.channelVolumes`/`mute`, the metadata
`default.audio.sink` key) is a property of PipeWire's own wire format, not
of this board specifically, and is what these captures actually ground.
