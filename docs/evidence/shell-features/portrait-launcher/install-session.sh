#!/usr/bin/env bash
# Narrow source-built userland deployment; survives shell restart, not reboot.
set -euo pipefail
config=/nix/store/83q3pzk9jyrwxckn05ybj7qn1k7fkqsr-k230-sway.conf
dropin=/run/systemd/system/shell.service.d/40-touch-launcher.conf
[ "$(readlink -f /run/current-system)" = /nix/store/07qjn49hhr8m57x4afiapaxdxngl44zp-nixos-system-nixos-26.11.20260919.20b1ddd ]
[ ! -e "$dropin" ] && [ ! -L "$dropin" ]
nix-store --import < /tmp/k230-launcher-final-config.nar
nix-store --add-root /nix/var/nix/gcroots/k230-launcher-trial --realise "$config"
mkdir -p /run/systemd/system/shell.service.d
cat > "$dropin" <<CONF
[Service]
ExecStart=
ExecStart=/nix/store/0dw6pla4d4qqyndk77mhahijjzv4g81v-sway-1.12/bin/sway -d -c $config
CONF
systemctl daemon-reload
systemctl restart shell
sleep 4
systemctl is-active shell
systemctl show shell -p ExecStart -p DropInPaths --no-pager
echo LAUNCHER_SESSION_INSTALLED
# Rollback: remove this exact drop-in, daemon-reload, restart shell.
# No kernel, bootloader, system profile, or boot files are changed here.
