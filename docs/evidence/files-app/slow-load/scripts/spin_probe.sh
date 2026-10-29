#!/bin/sh
# spin_probe.sh KIND SECONDS: run the spinner window with WAYLAND_DEBUG and summarise damage.
export GSK_RENDERER=cairo GDK_BACKEND=wayland GI_TYPELIB_PATH=${GIP:+$GIP:}$(cat /var/tmp/gi_typelib_path)
sudo -u shell env XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1 HOME=/home/shell ${LDP:+LD_LIBRARY_PATH=$LDP} GSK_RENDERER=cairo GI_TYPELIB_PATH=$GI_TYPELIB_PATH WAYLAND_DEBUG=client /nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 /var/tmp/spin_probe.py "$1" "$2" > /var/tmp/spin-wl.log 2>&1
grep -v "^\[" /var/tmp/spin-wl.log | head -5
grep -o "damage_buffer([^)]*)" /var/tmp/spin-wl.log | sort | uniq -c | sort -rn | head -6
