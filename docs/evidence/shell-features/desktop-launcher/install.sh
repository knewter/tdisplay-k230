set -e
export SYSTEMD_PAGER=cat PAGER=cat
nix-store --import < /tmp/k230-discovery.nar
nix-store --add-root /nix/var/nix/gcroots/k230-discovery-trial --realise /nix/store/hxjz1b7cy2j0ylakkr0yysyflhp3q0d7-k230-sway.conf
grep -q '83q3pzk9jyrwxckn05ybj7qn1k7fkqsr' /run/systemd/system/shell.service.d/40-touch-launcher.conf
sed -i 's/83q3pzk9jyrwxckn05ybj7qn1k7fkqsr/hxjz1b7cy2j0ylakkr0yysyflhp3q0d7/' /run/systemd/system/shell.service.d/40-touch-launcher.conf
systemctl daemon-reload
systemctl restart shell
sleep 4
systemctl is-active shell
systemctl show shell -p ExecStart -p DropInPaths --no-pager
echo DISCOVERY_INSTALLED
