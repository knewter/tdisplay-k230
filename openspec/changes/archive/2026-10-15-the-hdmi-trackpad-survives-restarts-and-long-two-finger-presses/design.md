## Context

`shell_ipc::run` keeps one Unix socket to sway. A `begin` whose command fails
clears the socket and reports the gesture as refused, so the gate passes it to
libinput as an ordinary touchpad stream. The socket is reopened only for the
next gesture. `gestures::Gate` buffers a new contact as a `Candidate`: a lone
contact times out after `PAIR_MS` (45 ms), and a multi-finger one after
`DECIDE_MS` (250 ms). A timed-out candidate is flushed to the virtual
touchpad with its source timestamps, which uinput passes on (the gate's tests
check this), so libinput measures every touch by its real duration.

## Decisions

1. **Retry `begin` once on an I/O error.** Reconnect and resend the same
   command, so the sequence number and timestamps are unchanged. A refusal
   (`success: false`) is not retried.
2. **No timeout for a still multi-finger candidate.** Movement still starts a
   shell pan (or a libinput scroll if the shell refuses it), and a spread
   change or contact-count change still flushes. `MAX_BUFFER` still bounds a
   very long hold. A one-finger candidate keeps its 45 ms pairing window, so
   pointer motion is not delayed.
3. **Re-time a lifted still press as a tap.** When the candidate's contacts
   all lift, the buffered events are stamped `TAP_PRESENTED_US` (40 ms)
   before the lift frame, which keeps its own time. libinput then applies its
   own tap rules: two fingers are a secondary click and three a middle click.
   Only still presses are re-timed; a press that moved has already been
   handed to the shell or to libinput as motion.
