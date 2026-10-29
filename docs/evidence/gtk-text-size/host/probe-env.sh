#!/usr/bin/env bash
# Build the probe's closure from this repo's pinned nixpkgs and run probe.sh.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
paths=$(nix build --inputs-from "$here/../../../.." --no-link --print-out-paths \
  nixpkgs#python3Packages.pygobject3 nixpkgs#python3 nixpkgs#gtk4 nixpkgs#libadwaita \
  nixpkgs#gsettings-desktop-schemas nixpkgs#sway nixpkgs#pango.out nixpkgs#harfbuzz \
  nixpkgs#gdk-pixbuf nixpkgs#glib.out nixpkgs#graphene nixpkgs#gobject-introspection \
  nixpkgs#gtk3 nixpkgs#atk nixpkgs#at-spi2-core)
typelibs= ; py= ; bin= ; schema=
for p in $paths; do
  [ -d "$p/lib/girepository-1.0" ] && typelibs="$typelibs:$p/lib/girepository-1.0"
  for s in "$p"/lib/python3*/site-packages; do [ -d "$s" ] && py="$py:$s"; done
  [ -d "$p/bin" ] && bin="$bin:$p/bin"
  for d in "$p"/share/gsettings-schemas/gsettings-desktop-schemas*; do [ -d "$d/glib-2.0/schemas" ] && schema=$d; done
done
PATH="${bin#:}:$PATH" PYTHONPATH="${py#:}" GI_TYPELIB_PATH="${typelibs#:}" SCHEMA_DIR="$schema" \
  "$here/probe.sh"
