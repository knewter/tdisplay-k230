#!/usr/bin/env bash
# Exercises the shell blocks in docs/wifi-runtime-secret.md without touching
# /run or starting a radio daemon.
set -euo pipefail

if test "$(id -u)" -ne 0; then
  exec unshare -Ur -- "$0"
fi

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
procedure="$repo_root/docs/wifi-runtime-secret.md"
test "$(id -u)" -eq 0

test_root=$(mktemp -d)
trap 'kill "${unrelated_pid:-}" 2>/dev/null || true; rm -rf "$test_root"' EXIT
fake_bin="$test_root/bin"
mkdir "$fake_bin"
printf '%s\n' \
  '#!/bin/sh' \
  'pidfile=' \
  'config=' \
  'logfile=' \
  'while test "$#" -gt 0; do' \
  '  case "$1" in' \
  '    -P) pidfile=$2; shift 2 ;;' \
  '    -c) config=$2; shift 2 ;;' \
  '    -f) logfile=$2; shift 2 ;;' \
  '    *) shift ;;' \
  '  esac' \
  'done' \
  'case "${WPA_FAKE_MODE:?}" in' \
  '  fail) exit 1 ;;' \
  '  dead)' \
  '    test -d "${WPA_EXPECT_CTRL:?}"' \
  '    test -d "${WPA_EXPECT_CLIENT:?}"' \
  '    test "$(/usr/bin/stat -c %a "$WPA_EXPECT_CTRL")" = 700' \
  '    test "$(/usr/bin/stat -c %a "$WPA_EXPECT_CLIENT")" = 700' \
  '    test "$(/usr/bin/stat -c %a "$logfile")" = 600' \
  '    grep -F -x -- "ctrl_interface=DIR=$WPA_EXPECT_CTRL GROUP=root" "$config" >/dev/null' \
  '    printf "%s\\n" 999999 > "$pidfile"; exit 0 ;;' \
  '  *) exit 2 ;;' \
  'esac' > "$fake_bin/wpa_supplicant"
chmod 755 "$fake_bin/wpa_supplicant"
printf '%s\n' \
  '#!/bin/sh' \
  'if test "${WPA_FAKE_NONROOT_SOURCE:-}" = 1 && test "$1" = -c && test "$2" = %u; then' \
  '  printf "%s\\n" 1' \
  '  exit 0' \
  'fi' \
  'exec /usr/bin/stat "$@"' > "$fake_bin/stat"
chmod 755 "$fake_bin/stat"
extract_block() {
  awk -v wanted="$1" '
    /^```sh/ { block++; next }
    /^```/ { if (block == wanted) exit }
    block == wanted { print }
  ' "$procedure"
}

run_setup() {
  extract_block 2 \
    | sed "s|/run/|$test_root/run/|g" \
    | env PATH="$fake_bin:$PATH" \
        RUNTIME_SECRET_FILE="$source_file" WIFI_IFACE=test0 \
        WPA_FAKE_MODE="$1" WPA_FAKE_NONROOT_SOURCE="${2:-}" \
        WPA_EXPECT_CTRL="$runtime_ctrl" WPA_EXPECT_CLIENT="$runtime_client" bash
}

run_completion() {
  extract_block 3 | sed "s|/run/|$test_root/run/|g" | bash
}

runtime_dir="$test_root/run"
runtime_conf="$runtime_dir/wpa-supplicant-board.conf"
runtime_pid="$runtime_dir/wpa-supplicant-board.pid"
runtime_ctrl="$runtime_dir/wpa_supplicant"
runtime_client="$runtime_ctrl/client"
runtime_log="$runtime_dir/wpa-supplicant-board.log"
mkdir "$runtime_dir"
source_file="$test_root/operator.conf"
printf '%s\n' \
  "ctrl_interface=DIR=$runtime_ctrl GROUP=root" \
  placeholder-only > "$source_file"
chmod 600 "$source_file"
chown 0:0 "$source_file"

# The documented source-owner check rejects a non-root input before a copy.
# A user namespace has only UID 0 mapped, so the test double reports UID 1
# only for this one stat query while all later mode checks use real stat.
if run_setup fail 1; then
  echo "non-root source unexpectedly accepted" >&2
  exit 1
fi
test ! -e "$runtime_conf"
test ! -e "$runtime_pid"
test ! -e "$runtime_ctrl"
test ! -e "$runtime_log"

# A failed daemon start triggers removal of the copied secret and PID path.
if run_setup fail; then
  echo "failed daemon start unexpectedly succeeded" >&2
  exit 1
fi
test ! -e "$runtime_conf"
test ! -e "$runtime_pid"
test ! -e "$runtime_ctrl"
test ! -e "$runtime_log"

# The control directive is mandatory and a missing directive cleans every
# runtime artifact after the protected file has been copied.
printf '%s\n' placeholder-only > "$source_file"
if run_setup dead; then
  echo "missing control directive unexpectedly accepted" >&2
  exit 1
fi
test ! -e "$runtime_conf"
test ! -e "$runtime_pid"
test ! -e "$runtime_ctrl"
test ! -e "$runtime_log"
printf '%s\n' \
  "ctrl_interface=DIR=$runtime_ctrl GROUP=root" \
  placeholder-only > "$source_file"

# A daemon that has exited before completion still permits removal of this
# invocation's files without signalling a reused or absent PID.
run_setup dead
test -e "$runtime_conf"
test -e "$runtime_pid"
test -d "$runtime_ctrl"
test -d "$runtime_client"
test -f "$runtime_log"
run_completion
test ! -e "$runtime_conf"
test ! -e "$runtime_pid"
test ! -e "$runtime_ctrl"
test ! -e "$runtime_log"

# Starting a second invocation refuses to overwrite existing state.
printf '%s\n' existing > "$runtime_conf"
printf '%s\n' 999999 > "$runtime_pid"
mkdir -p "$runtime_client"
printf '%s\n' existing-log > "$runtime_log"
if run_setup fail; then
  echo "existing runtime state unexpectedly accepted" >&2
  exit 1
fi
test "$(<"$runtime_conf")" = existing
test "$(<"$runtime_pid")" = 999999
test -d "$runtime_ctrl"
test -d "$runtime_client"
test "$(<"$runtime_log")" = existing-log
rm -rf "$runtime_conf" "$runtime_pid" "$runtime_ctrl" "$runtime_log"

# A live PID whose command line does not name this config cannot be killed or
# have its state removed by the explicit-completion block.
sleep 600 &
unrelated_pid=$!
printf '%s\n' unrelated > "$runtime_conf"
printf '%s\n' "$unrelated_pid" > "$runtime_pid"
if run_completion; then
  echo "unrelated PID unexpectedly accepted" >&2
  exit 1
fi
kill -0 "$unrelated_pid"
test -e "$runtime_conf"
test -e "$runtime_pid"
test ! -e "$runtime_ctrl"
test ! -e "$runtime_log"
rm -rf "$runtime_conf" "$runtime_pid"
kill "$unrelated_pid"
wait "$unrelated_pid" 2>/dev/null || true
unset unrelated_pid

# A live process that names the generated runtime configuration is stopped and
# its two runtime files are removed.
printf '%s\n' own > "$runtime_conf"
mkdir -m 700 "$runtime_ctrl"
mkdir -m 700 "$runtime_client"
printf '%s\n' owned-log > "$runtime_log"
tail -f "$runtime_conf" >/dev/null &
owned_pid=$!
printf '%s\n' "$owned_pid" > "$runtime_pid"
run_completion
# SIGTERM is asynchronous. Give the owned child a bounded 2 s to exit before
# declaring cleanup broken; do not apply this wait to the unrelated-PID case.
for _ in $(seq 1 40); do
  kill -0 "$owned_pid" 2>/dev/null || break
  sleep 0.05
done
if kill -0 "$owned_pid" 2>/dev/null; then
  echo "owned PID was not stopped" >&2
  exit 1
fi
wait "$owned_pid" 2>/dev/null || true
test ! -e "$runtime_conf"
test ! -e "$runtime_pid"
test ! -e "$runtime_ctrl"
test ! -e "$runtime_log"

echo "Wi-Fi runtime-secret procedure tests passed"
