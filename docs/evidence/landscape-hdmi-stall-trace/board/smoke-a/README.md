# Isolated controller smoke

The installed RISC-V kernel 7.3.0-rc5 recorded 42 numeric events for the diagnostic
Python process. Harmless /dev/null operations established write 64/writev 66
(return 8 bytes each) and ioctl 29 (return -ENOTTY/-25). Both monotonic markers
were inside their recorded before/after brackets. Per-CPU loss counters are
zero. Cleanup removed the instance, stopped its 600 s timer and verified every
global tracing-control hash unchanged. No compositor workload was traced.

`raw.trace` remains private in the handoff scratch directory; its SHA256 and
byte count are recorded in `trace.json`. `events.jsonl` is the public numeric
export and omits registers holding pointers, buffers and process names. The
exact command is in `command.json`; helper source ce88a724 is identified by
its full tool SHA256 in `smoke.json`.
