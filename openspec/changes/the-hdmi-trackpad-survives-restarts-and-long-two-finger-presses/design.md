## Context

`shell_ipc::run` keeps one Unix socket to sway. A `begin` whose command fails
clears the socket and reports the gesture as refused, so the gate passes it to
libinput as an ordinary touchpad stream. The socket is reopened only for the
next gesture. `gestures::Gate` buffers a new contact as a `Candidate`: a lone
contact times out after `PAIR_MS` (45 ms), and a multi-finger one after
`DECIDE_MS` (250 ms). A timed-out candidate is flushed to the virtual
touchpad. uinput stamps events at write time, so libinput's tap timer starts
at the flush.

## Decisions

1. **Retry `begin` once on an I/O error.** Reconnect and resend the same
   command, so the sequence number and timestamps are unchanged. A refusal
   (`success: false`) is not retried.
2. **No timeout for a still multi-finger candidate.** Movement still starts a
   shell pan (or a libinput scroll if the shell refuses it), and a spread
   change or contact-count change still flushes. `MAX_BUFFER` still bounds a
   very long hold. A one-finger candidate keeps its 45 ms pairing window, so
   pointer motion is not delayed.
