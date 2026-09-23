#!/bin/sh
# Create board-local fixtures for production touch-launcher stale/empty checks.
# Usage ON THE BOARD:
#   REAL_SWAYMSG=/nix/store/...-sway/bin/swaymsg K230_JQ=/nix/store/...-jq/bin/jq \
#     sh /run/k230-overview-fixtures.sh /run/k230-overview-fixtures
# The fixtures emit only a synthetic label and never write real window titles.
set -eu
out=${1:?usage: $0 OUTPUT_DIRECTORY}
: "${REAL_SWAYMSG:?set absolute real swaymsg path}"
: "${K230_JQ:?set absolute jq path}"
mkdir -p "$out"
chmod 755 "$out"
cat > "$out/empty-catalog" <<'SCRIPT'
#!/bin/sh
# A valid, empty metadata reply: stdout intentionally contains no rows.
exit 0
SCRIPT
cat > "$out/stale-catalog" <<'SCRIPT'
#!/bin/sh
set -eu
id=$("$REAL_SWAYMSG" -t get_tree -r | "$K230_JQ" -r '
  recurse(.nodes[]?, .floating_nodes[]?) |
  select(.app_id? == "k230-stale-fixture") | .id
' | head -n 1)
# The first query lists only the disposable Foot window. After its owner kills
# that process, the revalidation query succeeds with zero rows.
if [ -n "$id" ] && [ "$id" != null ]; then
  printf '%s\tFixture\tk230-stale-fixture\tnormal\n' "$id"
fi
SCRIPT
cat > "$out/focus-log-swaymsg" <<'SCRIPT'
#!/bin/sh
# The launcher invokes this only for a revalidated focus. Do not use it for
# catalog enumeration; stale-catalog uses REAL_SWAYMSG directly.
printf '%s\n' "$*" >> "${K230_FOCUS_LOG:?}"
exec "$REAL_SWAYMSG" "$@"
SCRIPT
chmod 755 "$out/empty-catalog" "$out/stale-catalog" "$out/focus-log-swaymsg"
printf '%s\n' "fixtures written to $out"
