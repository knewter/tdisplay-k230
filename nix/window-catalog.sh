#!/usr/bin/env bash
# Read-only metadata for the native window overview. No titles become commands.
set -euo pipefail
: "${K230_SWAYMSG:=swaymsg}"
: "${K230_JQ:=jq}"
"$K230_SWAYMSG" -t get_tree -r | "$K230_JQ" -r '
  def text: if type == "string" then gsub("[\u0000-\u001f\u007f]"; " ") else "" end;
  if type != "object" or .type != "root" then error("invalid Sway tree") else . end |
  recurse(.nodes[]?, .floating_nodes[]?) |
  select(.type == "con" or .type == "floating_con") |
  select((.nodes // [] | length) == 0 and (.floating_nodes // [] | length) == 0) |
  select(.app_id != null or .window != null or .pid != null) |
  select(.id | type == "number" and . > 0 and . == floor) |
  [(.id | tostring), (.name | text), ((.app_id // .window_properties.class) | text),
   ([if .focused then "focused" else empty end,
     if .urgent then "urgent" else empty end,
     if (.fullscreen_mode // 0) > 0 then "fullscreen" else empty end] |
    if length == 0 then "normal" else join(",") end)] | join("\t")'
