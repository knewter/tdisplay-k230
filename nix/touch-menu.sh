#!/usr/bin/env bash
# The wrapper in shell.nix supplies the absolute Nix store paths. Keeping the
# state machine here makes its i3bar protocol and privileged actions testable
# without building a NixOS closure.
set -u

: "${K230_SWAYMSG:=swaymsg}"
: "${K230_FOOT:=foot}"
: "${K230_HTOP:=htop}"
: "${K230_HTOPRC:?K230_HTOPRC is required}"
: "${K230_JQ:=jq}"
: "${K230_SED:=sed}"
: "${K230_PKILL:=pkill}"
: "${K230_SUDO:=/run/wrappers/bin/sudo}"
: "${K230_SYSTEMCTL:=systemctl}"
: "${K230_TERMINAL_CONFIG:?K230_TERMINAL_CONFIG is required}"
: "${K230_MONITOR_CONFIG:?K230_MONITOR_CONFIG is required}"

page=home
window_offset=0

# Keep the home and Apps surfaces visually related without a theme framework.
menu_foreground='#ffffff'
menu_apps='#2f6b4f'
menu_windows='#2b547c'
menu_keyboard='#6b4f2b'
menu_system='#5e3d61'
menu_monitor='#245f7a'
menu_new_terminal='#396b57'
menu_back='#3b3f46'

windows_json() {
  "$K230_SWAYMSG" -t get_tree -r | "$K230_JQ" -c --argjson offset "$window_offset" '
    [recurse(.nodes[]?, .floating_nodes[]?)
     | select(.type == "con" and (.app_id? != null or .pid? != null))
     | { name: ("window:" + (.id | tostring)),
         full_text: ((.name // .app_id // "Window")[0:12]),
         min_width: 128, align: "center", separator: false,
         separator_block_width: 0 }]
    | .
  ' 2>/dev/null || printf '[]\n'
}

emit() {
  case "$page" in
    home)
      printf '%s\n' "[{\"name\":\"apps\",\"full_text\":\"Apps\",\"min_width\":128,\"align\":\"center\",\"color\":\"$menu_foreground\",\"background\":\"$menu_apps\",\"separator\":false,\"separator_block_width\":0},{\"name\":\"windows\",\"full_text\":\"Windows\",\"min_width\":128,\"align\":\"center\",\"color\":\"$menu_foreground\",\"background\":\"$menu_windows\",\"separator\":false,\"separator_block_width\":0},{\"name\":\"keyboard\",\"full_text\":\"Keyboard\",\"min_width\":128,\"align\":\"center\",\"color\":\"$menu_foreground\",\"background\":\"$menu_keyboard\",\"separator\":false,\"separator_block_width\":0},{\"name\":\"system\",\"full_text\":\"System\",\"min_width\":128,\"align\":\"center\",\"color\":\"$menu_foreground\",\"background\":\"$menu_system\",\"separator\":false,\"separator_block_width\":0}],"
      ;;
    apps)
      printf '%s\n' "[{\"name\":\"terminal\",\"full_text\":\"Terminal\",\"min_width\":128,\"align\":\"center\",\"color\":\"$menu_foreground\",\"background\":\"$menu_apps\",\"separator\":false,\"separator_block_width\":0},{\"name\":\"monitor\",\"full_text\":\"Monitor\",\"min_width\":128,\"align\":\"center\",\"color\":\"$menu_foreground\",\"background\":\"$menu_monitor\",\"separator\":false,\"separator_block_width\":0},{\"name\":\"new-terminal\",\"full_text\":\"New term\",\"min_width\":128,\"align\":\"center\",\"color\":\"$menu_foreground\",\"background\":\"$menu_new_terminal\",\"separator\":false,\"separator_block_width\":0},{\"name\":\"back\",\"full_text\":\"Back\",\"min_width\":128,\"align\":\"center\",\"color\":\"$menu_foreground\",\"background\":\"$menu_back\",\"separator\":false,\"separator_block_width\":0}],"
      ;;
    windows)
      all_windows=$(windows_json)
      window_count=$(printf '%s\n' "$all_windows" | "$K230_JQ" 'length')
      if [ "$window_count" -eq 0 ]; then
        printf '%s\n' '[{"name":"no-windows","full_text":"No windows","min_width":178,"align":"center","separator":false,"separator_block_width":0},{"name":"home","full_text":"Home","min_width":178,"align":"center","separator":false,"separator_block_width":0},{"name":"back","full_text":"Back","min_width":178,"align":"center","separator":false,"separator_block_width":0}],'
      else
        window_offset=$((window_offset % window_count))
        "$K230_JQ" -cn --argjson windows "$all_windows" --argjson offset "$window_offset" '
          $windows[$offset:($offset + 1)] + [
            {name: "home", full_text: "Home", min_width: 128, align: "center", separator: false, separator_block_width: 0},
            {name: "next-windows", full_text: "Next", min_width: 128, align: "center", separator: false, separator_block_width: 0},
            {name: "back", full_text: "Back", min_width: 128, align: "center", separator: false, separator_block_width: 0}
          ]
        ' | "$K230_SED" 's/$/,/'
      fi
      ;;
    system)
      printf '%s\n' '[{"name":"reboot","full_text":"Reboot","min_width":178,"align":"center","separator":false,"separator_block_width":0},{"name":"poweroff","full_text":"Power off","min_width":178,"align":"center","separator":false,"separator_block_width":0},{"name":"back","full_text":"Back","min_width":178,"align":"center","separator":false,"separator_block_width":0}],'
      ;;
    confirm-reboot)
      printf '%s\n' '[{"name":"confirm-reboot","full_text":"Reboot now","min_width":270,"align":"center","separator":false,"separator_block_width":0},{"name":"cancel","full_text":"Cancel","min_width":270,"align":"center","separator":false,"separator_block_width":0}],'
      ;;
    confirm-poweroff)
      printf '%s\n' '[{"name":"confirm-poweroff","full_text":"Power off","min_width":270,"align":"center","separator":false,"separator_block_width":0},{"name":"cancel","full_text":"Cancel","min_width":270,"align":"center","separator":false,"separator_block_width":0}],'
      ;;
    system-error)
      printf '%s\n' '[{"name":"retry-system","full_text":"Action failed","min_width":178,"align":"center","separator":false,"separator_block_width":0},{"name":"system","full_text":"Try again","min_width":178,"align":"center","separator":false,"separator_block_width":0},{"name":"back","full_text":"Back","min_width":178,"align":"center","separator":false,"separator_block_width":0}],'
      ;;
  esac
}

start_terminal() {
  "$K230_FOOT" --config "$K230_TERMINAL_CONFIG" >/dev/null 2>&1 &
}

present_or_start() {
  app_id="$1"
  config="$2"
  if "$K230_SWAYMSG" -t get_tree -r | "$K230_JQ" -e --arg app_id "$app_id" \
      'recurse(.nodes[]?, .floating_nodes[]?) | select(.app_id? == $app_id) | .id' \
      >/dev/null 2>&1; then
    "$K230_SWAYMSG" "[app_id=\"$app_id\"] focus" >/dev/null
  elif [ "$app_id" = k230-monitor ]; then
    HTOPRC="$K230_HTOPRC" "$K230_FOOT" --config "$config" -e "$K230_HTOP" >/dev/null 2>&1 &
  else
    start_terminal
  fi
}

run_system_action() {
  if "$K230_SUDO" -n "$K230_SYSTEMCTL" "$1" >/dev/null 2>&1; then
    page=home
  else
    page=system-error
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
    new-terminal) start_terminal; page=home ;;
    window:*)
      con_id=${name#window:}
      case "$con_id" in
        *[!0-9]*|'') ;;
        *) "$K230_SWAYMSG" "[con_id=$con_id] focus" >/dev/null ;;
      esac
      page=home
      ;;
    next-windows)
      if [ "$window_count" -gt 0 ]; then
        window_offset=$(((window_offset + 1) % window_count))
      fi
      ;;
    reboot) page=confirm-reboot ;;
    poweroff) page=confirm-poweroff ;;
    confirm-reboot) [ "$page" = confirm-reboot ] && run_system_action reboot ;;
    confirm-poweroff) [ "$page" = confirm-poweroff ] && run_system_action poweroff ;;
    retry-system) [ "$page" = system-error ] && page=system ;;
    back|cancel) page=home ;;
  esac
  emit
done
