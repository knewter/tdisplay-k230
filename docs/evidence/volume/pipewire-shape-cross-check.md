# PipeWire wire-shape and command-syntax cross-check

Evidence class: **dev-host PipeWire session** -- a real, running PipeWire
1.6.8 daemon on this repository's own development machine (not the K230
board, not QEMU). This class grounds wire-format and command-syntax
questions, because PipeWire is the same software regardless of host, but it
proves nothing about this board's audio hardware, ALSA card, or any
hardware volume key -- those stay open board tasks (`tasks.md`, group 7).
No real device on the host session used for this check was muted, had its
volume changed, or was otherwise disturbed; every write below targeted a
throwaway virtual sink created and removed for this check alone, and no
hostname, username, or real stream/app name from the host is reproduced
here.

## Method

```sh
pactl load-module module-null-sink sink_name=k230_volume_probe \
  sink_properties=device.description=K230_Volume_Probe
# -> module id, e.g. 536870914
pw-cli ls Node | grep -B6 k230_volume_probe   # -> the node's PipeWire id
wpctl set-volume <id> 0.58
pw-dump | <extract Props for <id>>
wpctl set-mute <id> 1
pw-dump | <extract Props for <id>>
pactl unload-module <module id>               # cleanup
```

## Findings

1. **`application.icon-name` (hyphenated) is the real key**, matching
   `PW_KEY_APP_ICON_NAME` in PipeWire's own `pipewire/keys.h` -- confirmed
   directly against real `Stream/Output/Audio` nodes on the host session
   (several real desktop apps' own icon names were visible with this exact
   key spelling; not reproduced here). An earlier draft of this shell's own
   parser looked for the underscored `application.icon_name`, which never
   matches a real dump.
2. **A `Props` param's relevant keys** are `volume`, `mute`, `channelVolumes`,
   `channelMap`, plus PipeWire's own `softMute`/`softVolumes`/
   `monitorMute`/`monitorVolumes` this shell does not use.
3. **The perceptual curve is confirmed, measured directly**: `wpctl
   set-volume <id> 0.58` against a throwaway node produced
   `channelVolumes: [0.195112, 0.195112]`. `0.58^3 = 0.19511199999999995`,
   matching to the precision `wpctl` itself prints. `wpctl` already applies
   the same cubic taper this change's own `volume::percent_to_linear`
   implements; the two must (and do) agree.
4. **Mute is independent of level, confirmed directly**: `wpctl set-mute <id>
   1` against the same node changed only `mute: true`; `channelVolumes`
   stayed exactly `[0.195112, 0.195112]`.
5. **`default.audio.sink` metadata's `value` arrives as an already-parsed
   JSON object** (`{"name": "..."}`), not a JSON-encoded string, in a real
   `pw-dump`/`pw-metadata` capture on this PipeWire version, even though its
   own `type` field reads `Spa:String:JSON`. `pipewire_ipc.rs`'s
   `default_sink_name` reads it as an object for this reason.
6. **`pw-cli`'s scripting/stdin mode** does read and execute one command per
   line with no tty (`printf 'info 0\n' | pw-cli` produced a normal banner
   and command response, then continued reading further lines), and its
   `help` output documents `set-param | s   Set param of an object
   <object-id> <param-id> <param-json>` -- the exact form
   `pipewire_ipc::set_volume_command` emits (`s <id> Props '{...}'`).
7. **A freshly-connected `pw-cli` does not yet know about objects that
   existed before it connected**, until its own registry sync catches up
   (`s <existing-id> ...` issued immediately after connecting returned
   `Error: "s: unknown global '<id>'"`). This matters once, at this shell's
   own startup when its persistent `pw-cli` first connects, not per write --
   the process stays connected and registry-synced for its whole life
   after that.
8. **`pw-metadata`'s CLI form** is `pw-metadata [id [key [value [type]]]]`;
   a real invocation with no arguments printed the current `default` metadata
   set including `default.audio.sink`/`default.audio.source`, confirming
   `default.audio.sink`'s key name and value shape match point 5.

## Limits

Host-PipeWire-grounded only. Proves the wire shape and command syntax this
shell's parser and writer assume are correct against a real PipeWire
daemon; proves nothing about the K230's own ALSA card, kernel driver, or
whether any of this is reachable/correct once cross-compiled and run on
that board. Task groups 6 and 7 in `tasks.md` carry the QEMU and board
proof this file does not.
