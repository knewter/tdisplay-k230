{ runCommand, themedFoot, foot, htop, nnn }:

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
EOF
  cat > "$out/share/applications/nnn.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Files
GenericName=File Manager
Comment=Browse files in a terminal
Exec=${nnn}/bin/nnn %f
Icon=folder
Terminal=true
MimeType=inode/directory;
Categories=System;FileTools;FileManager;
EOF
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
