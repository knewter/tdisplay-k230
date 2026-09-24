#!/usr/bin/env bash
# Verifies the host-side persistent Wi-Fi service contract without a board,
# image build, credential, or radio daemon.
set -euo pipefail

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

service=$(nix eval --json .#nixosConfigurations.k230.config.systemd.services.k230-wifi.serviceConfig)
unit=$(nix eval --json .#nixosConfigurations.k230.config.systemd.services.k230-wifi.unitConfig)
wanted_by=$(nix eval --json .#nixosConfigurations.k230.config.systemd.services.k230-wifi.wantedBy)
requires=$(nix eval --json .#nixosConfigurations.k230.config.systemd.services.k230-wifi.requires)
binds_to=$(nix eval --json .#nixosConfigurations.k230.config.systemd.services.k230-wifi.bindsTo)
after=$(nix eval --json .#nixosConfigurations.k230.config.systemd.services.k230-wifi.after)
before=$(nix eval --json .#nixosConfigurations.k230.config.systemd.services.k230-wifi.before)
tmpfiles=$(nix eval --json .#nixosConfigurations.k230.config.systemd.tmpfiles.rules)

jq -e '.LoadCredential == "wpa_supplicant.conf:/var/lib/k230/wifi/wpa_supplicant.conf"
  and .RuntimeDirectory == "k230-wifi"
  and .RuntimeDirectoryMode == "0700"
  and .UMask == "0077"
  and .StandardOutput == "null"
  and .StandardError == "null"
  and .Restart == "on-failure"' <<<"$service" >/dev/null
jq -e '.ConditionPathExists == "/var/lib/k230/wifi/wpa_supplicant.conf"' <<<"$unit" >/dev/null
jq -n -e \
  --argjson wanted_by "$wanted_by" \
  --argjson requires "$requires" \
  --argjson binds_to "$binds_to" \
  --argjson after "$after" \
  --argjson before "$before" \
  '$wanted_by == ["multi-user.target"]
  and ($requires | index("sys-subsystem-net-devices-wlan0.device"))
  and ($binds_to | index("sys-subsystem-net-devices-wlan0.device"))
  and ($after | index("local-fs.target"))
  and ($after | index("sys-subsystem-net-devices-wlan0.device"))
  and ($before | index("network-online.target"))' >/dev/null
jq -e 'index("d /var/lib/k230 0700 root root -")
  and index("d /var/lib/k230/wifi 0700 root root -")' <<<"$tmpfiles" >/dev/null

rg -q --fixed-strings 'LoadCredential = "wpa_supplicant.conf:/var/lib/k230/wifi/wpa_supplicant.conf"' nix/hardware.nix
rg -q --fixed-strings 'wpa_cli -s /run/k230-wifi/wpa_supplicant/client' docs/wifi-persistent-credential.md
rg -q --fixed-strings -- '-p /run/k230-wifi/wpa_supplicant -i wlan0 status' docs/wifi-persistent-credential.md
if rg -n -i '^[[:space:]]*(ssid|psk|password)=' nix docs/wifi-persistent-credential.md; then
  echo "protected-network material appeared in tracked persistent configuration" >&2
  exit 1
fi

echo "Persistent Wi-Fi service host checks passed"
