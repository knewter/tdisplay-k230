# Injected uinput actions on the physical board.
swaymsg '[app_id="k230-monitor"] kill'; swaymsg 'exec HTOPRC=/tmp/k230-monitor.htoprc foot --app-id=k230-monitor --title=Monitor --font="DejaVu Sans Mono:size=15" htop'; sleep 5; grim /tmp/monitor-portrait.png
