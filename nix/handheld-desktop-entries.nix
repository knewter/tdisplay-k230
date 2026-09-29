{ lib, runCommand, themedFoot, foot, htop, portfolioLauncher, nautilusLauncher ? null }:

# Desktop-entry overrides have the same IDs as upstream packages. Putting this
# share tree first in XDG_DATA_DIRS lets GIO apply the normal freedesktop
# precedence/NoDisplay rules; the Rust catalog never filters app names.
runCommand "k230-handheld-desktop-entries" { } ''
  mkdir -p "$out/share/applications"
  cat > "$out/share/applications/foot.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Terminal
GenericName=Terminal
Comment=Open a terminal
Exec=${themedFoot}/bin/k230-foot terminal
Icon=foot
Terminal=false
Categories=System;TerminalEmulator;
StartupWMClass=k230-terminal
EOF
  cat > "$out/share/applications/htop.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Monitor
GenericName=Process Viewer
Comment=View system processes
Exec=${themedFoot}/bin/k230-foot monitor -e ${htop}/bin/htop
Icon=htop
Terminal=false
Categories=System;Monitor;
StartupWMClass=k230-monitor
EOF
  cat > "$out/share/applications/dev.tchx84.Portfolio.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Files (Portfolio)
GenericName=File Manager
Comment=Touch-first GTK4/libadwaita file manager
Exec=${portfolioLauncher}/bin/k230-portfolio %U
Icon=dev.tchx84.Portfolio
Terminal=false
MimeType=inode/directory;
Categories=System;FileTools;FileManager;
StartupWMClass=dev.tchx84.Portfolio
EOF
  ${lib.optionalString (nautilusLauncher != null) ''
  cat > "$out/share/applications/org.gnome.Nautilus.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Files (Nautilus)
GenericName=File Manager
Comment=GNOME's file manager, Omarchy's own default
Exec=${nautilusLauncher}/bin/k230-nautilus %U
Icon=org.gnome.Nautilus
Terminal=false
MimeType=inode/directory;
Categories=System;FileTools;FileManager;
StartupWMClass=org.gnome.Nautilus
EOF
  ''}
  cat > "$out/share/applications/footclient.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Foot Client
Exec=${foot}/bin/footclient
Icon=foot
Terminal=false
NoDisplay=true
Categories=System;TerminalEmulator;
EOF
  cat > "$out/share/applications/foot-server.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Foot Server
Exec=${foot}/bin/foot --server
Icon=foot
Terminal=false
NoDisplay=true
Categories=System;TerminalEmulator;
EOF
''
