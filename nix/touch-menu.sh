#!/usr/bin/env bash
# The wrapper in shell.nix supplies the absolute Nix store paths. Keeping the
# state machine here makes its i3bar protocol and privileged actions testable
# without building a NixOS closure.
set -u

: "${K230_SWAYMSG:=swaymsg}"
: "${K230_FOOT:=foot}"
: "${K230_HTOP:=htop}"
: "${K230_JQ:=jq}"
: "${K230_SED:=sed}"
: "${K230_PKILL:=pkill}"
: "${K230_SUDO:=/run/wrappers/bin/sudo}"
: "${K230_SYSTEMCTL:=systemctl}"
: "${K230_TERMINAL_CONFIG:?K230_TERMINAL_CONFIG is required}"
: "${K230_MONITOR_CONFIG:?K230_MONITOR_CONFIG is required}"

page=home
window_offset=0

window_blocks() {
  "$K230_SWAYMSG" -t get_tree -r | "$K230_JQ" -c --argjson offset "$window_offset" '
    [recurse(.nodes[]?, .floating_nodes[]?)
     | select(.type == "con" and (.app_id? != null or .pid? != null))
     | { name: ("window:" + (.id | tostring)),
         full_text: ((.name // .app_id // "Window")[0:12]),
         min_width: 128, align: "center", separator: false,
         separator_block_width: 0 }]
    | .[$offset:($offset + 1)]
  ' 2>/dev/null || printf '[]\n'
}

emit() {
  case "$page" in
    home)
      printf '%s\n' '[{"name":"apps","full_text":"Apps","min_width":128,"align":"center","separator":false,"separator_block_width":0},{"name":"windows","full_text":"Windows","min_width":128,"align":"center","separator":false,"separator_block_width":0},{"name":"keyboard","full_text":"Keyboard","min_width":128,"align":"center","separator":false,"separator_block_width":0},{"name":"system","full_text":"System","min_width":128,"align":"center","separator":false,"separator_block_width":0}],'
      ;;
    apps)
      printf '%s\n' '[{"name":"terminal","full_text":"Terminal","min_width":178,"align":"center","separator":false,"separator_block_width":0},{"name":"monitor","full_text":"Monitor","min_width":178,"align":"center","separator":false,"separator_block_width":0},{"name":"back","full_text":"Back","min_width":178,"align":"center","separator":false,"separator_block_width":0}],'
      ;;
    windows)
      blocks=$(window_blocks)
      "$K230_JQ" -cn --argjson blocks "$blocks" --arg next "Next" '
        $blocks + [
          {name: "home", full_text: "Home", min_width: 128, align: "center", separator: false, separator_block_width: 0},
          {name: "next-windows", full_text: $next, min_width: 128, align: "center", separator: false, separator_block_width: 0},
          {name: "back", full_text: "Back", min_width: 128, align: "center", separator: false, separator_block_width: 0}
        ]
      ' | "$K230_SED" 's/$/,/'
      ;;
    system)
      printf '%s\n' '[{"name":"reboot","full_text":"Reboot","min_width":178,"align":"center","separator":false,"separator_block_width":0},{"name":"poweroff","full_text":"Power off","min_width":178,"align":"center","separator":false,"separator_block_width":0},{"name":"back","full_text":"Back","min_width":178,"align":"center","separator":false,"separator_block_width":0}],'
      ;;
    confirm-reboot)
      printf '%s\n' '[{"name":"confirm-reboot","full_text":"Confirm","min_width":270,"align":"center","separator":false,"separator_block_width":0},{"name":"cancel","full_text":"Cancel","min_width":270,"align":"center","separator":false,"separator_block_width":0}],'
      ;;
    confirm-poweroff)
      printf '%s\n' '[{"name":"confirm-poweroff","full_text":"Confirm","min_width":270,"align":"center","separator":false,"separator_block_width":0},{"name":"cancel","full_text":"Cancel","min_width":270,"align":"center","separator":false,"separator_block_width":0}],'
      ;;
  esac
}

present_or_start() {
  app_id="$1"
  config="$2"
  if "$K230_SWAYMSG" -t get_tree -r | "$K230_JQ" -e --arg app_id "$app_id" \
      'recurse(.nodes[]?, .floating_nodes[]?) | select(.app_id? == $app_id) | .id' \
      >/dev/null 2>&1; then
    "$K230_SWAYMSG" "[app_id=\"$app_id\"] focus" >/dev/null
  elif [ "$app_id" = k230-monitor ]; then
    "$K230_FOOT" --config "$config" -e "$K230_HTOP" >/dev/null 2>&1 &
  else
    "$K230_FOOT" --config "$config" >/dev/null 2>&1 &
  fi
}

# i3bar's header and opening array are written exactly once. Every following
# line is an array element, including after a click.
printf '{"version":1,"click_events":true}\n[\n'
emit
while IFS= read -r line; do
  # Swaybar's JSON formatting is not part of its click-event contract. Extract
  # the fixed control name while accepting compact or whitespace-formatted JSON.
  name=$(printf '%s\n' "$line" | "$K230_SED" -n 's/.*"name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
  case "$name" in
    apps) page=apps ;;
    windows) page=windows; window_offset=0 ;;
    keyboard) "$K230_PKILL" -RTMIN -x wvkbd-mobintl ;;
    system) page=system ;;
    terminal|home) present_or_start k230-terminal "$K230_TERMINAL_CONFIG"; page=home ;;
    monitor) present_or_start k230-monitor "$K230_MONITOR_CONFIG"; page=home ;;
    window:*)
      con_id=${name#window:}
      case "$con_id" in
        *[!0-9]*|'') ;;
        *) "$K230_SWAYMSG" "[con_id=$con_id] focus" >/dev/null ;;
      esac
      page=home
      ;;
    next-windows) window_offset=$((window_offset + 1)) ;;
    reboot) page=confirm-reboot ;;
    poweroff) page=confirm-poweroff ;;
    confirm-reboot) exec "$K230_SUDO" -n "$K230_SYSTEMCTL" reboot ;;
    confirm-poweroff) exec "$K230_SUDO" -n "$K230_SYSTEMCTL" poweroff ;;
    back|cancel) page=home ;;
  esac
  emit
done
