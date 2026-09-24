# Wi-Fi runtime-secret synthetic CI fixture

On 2026-09-24, GitHub Actions run `35959460953` exited 1 in the
`Check Wi-Fi runtime secret cleanup` step. The only emitted line was
`existing Wi-Fi runtime state; complete or investigate it first`.
That line is the *expected* refusal in the second-invocation negative case;
the test had no phase label for a later `set -e` assertion, so the log does
not identify the exact failing assertion. No real Wi-Fi secret, device, or
radio was involved in this CI test.

The synthetic exited-daemon case previously wrote the fixed PID `999999`.
It is not guaranteed absent on a busy CI host, so a live process with that
PID could change the completion branch. The fixture now selects
`/proc/sys/kernel/pid_max + 1`, which cannot be a live Linux PID. The test
also reports its active phase on failure, distinguishing the expected
existing-state refusal from any subsequent failure. The documented operator
procedure and its refusal/cleanup behavior are unchanged.

```text
bash -n tools/test-wifi-runtime-secret-procedure.sh
bash tools/test-wifi-runtime-secret-procedure.sh
  PASS (expected refusal line, then "Wi-Fi runtime-secret procedure tests passed")
for index in $(seq 1 50); do bash tools/test-wifi-runtime-secret-procedure.sh >/tmp/k230-wifi-secret-loop.log 2>&1 || exit 1; done
  PASS 50 synthetic user-namespace runs
```

The host fixture check does not reproduce the original CI failure; the exact
failing assertion remains unknown from that run's log. A fresh CI run must
establish whether the intermittent failure is resolved. If it recurs, the
new phase label provides the next bounded investigation target.
