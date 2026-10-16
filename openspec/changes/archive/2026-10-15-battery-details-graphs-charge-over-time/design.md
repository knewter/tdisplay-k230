## Context

`tick_home_widgets` already polls `/sys/class/power_supply` every 30 s, or
every 10 s while a Battery - Details widget is placed. Home layout state is
kept in `$XDG_STATE_HOME/k230-shell/home.json`. The board is often rebooted,
so a history held only in memory would usually be empty.

## Decisions

1. **Recorder in the shell, on the existing poll.** A sample is appended when
   at least 60 s have passed since the last one, or when the charging state
   changes. Each line of `battery-history` is
   `<unix seconds> <percent> <c|d>`. Lines that fail to parse are skipped.
2. **Bounded file.** On load and when the file passes 2x the 24 h budget
   (about 2880 lines), the shell drops samples older than 24 h and rewrites
   the file through a temporary file and a rename, as `home.json` does. At one
   short line per minute, writes stay small.
3. **Wall-clock timestamps.** Samples use Unix time, so history lines up across
   reboots. Samples dated in the future, which happens after a clock step, are
   dropped at load. A gap longer than 5 minutes between samples breaks the line.
4. **Graph placement.** The widget's hero row has free space to the right of the
   state and time text. The graph takes the right part of that row at the
   ring's height, with "12 h" and "now" captions. If the space is narrower than
   a minimum width, the graph is left out.
5. **Repaint.** The graph is redrawn only when a new sample is appended. That
   happens at most once a minute and on charging changes, so it adds no
   per-frame work.

## Risks / Trade-offs

- The shell does not record while it is not running, so the graph shows gaps
  rather than estimated values.
- The gauge's percentage moves in whole steps, so a short idle span is flat.
