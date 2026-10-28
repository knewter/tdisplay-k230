{ lib, runCommand, desktop-file-utils, themedFoot, foot, htop, btop, viewnior, coreutils, portfolioLauncher, nautilusLauncher ? null }:

# Desktop-entry overrides have the same IDs as upstream packages. Putting this
# share tree first in XDG_DATA_DIRS lets GIO apply the normal freedesktop
# precedence/NoDisplay rules; the Rust catalog never filters app names.
runCommand "k230-handheld-desktop-entries" { nativeBuildInputs = [ desktop-file-utils ]; } ''
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
  # 14 pt gives at least 24 rows in the 568 px landscape output (15 pt gives
  # 23), which btop's layout needs to keep its process list.
  cat > "$out/share/applications/btop.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=btop++
GenericName=System Monitor
Comment=Resource monitor that shows usage and stats for processor, memory, disks, network and processes
Exec=${themedFoot}/bin/k230-foot terminal --app-id=k230-btop "--font=DejaVu Sans Mono:size=14" -e ${btop}/bin/btop
Icon=btop
Terminal=false
Categories=System;Monitor;
Keywords=system;process;task
StartupWMClass=k230-btop
EOF
  # nixpkgs' wrapper defaults GDK_BACKEND to x11, and this image has no X server.
  cat > "$out/share/applications/viewnior.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Viewnior
Comment=Elegant Image Viewer
Exec=${coreutils}/bin/env GDK_BACKEND=wayland ${viewnior}/bin/viewnior %F
Icon=viewnior
StartupNotify=true
Terminal=false
Categories=GNOME;GTK;Graphics;Viewer;
MimeType=image/bmp;image/gif;image/jpeg;image/jpg;image/pjpeg;image/png;image/tiff;image/x-bmp;image/x-gray;image/x-icb;image/x-ico;image/x-png;image/x-portable-anymap;image/x-portable-bitmap;image/x-portable-graymap;image/x-portable-pixmap;image/x-xbitmap;image/x-xpixmap;image/x-pcx;image/svg+xml;image/svg+xml-compressed;image/vnd.wap.wbmp;
Keywords=Image;Picture;Slideshow;
EOF
  cat > "$out/share/applications/dev.tchx84.Portfolio.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Files (Portfolio)
NoDisplay=true
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
Name=Files
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
  # An index lets GIO associate these entries with their MimeType lines. Without
  # one, GIO treats this directory as unindexed and the system cache's
  # Viewnior and Files rows are dropped from `gio mime` (host evidence in
  # docs/evidence/open-with/host/gio-mime.txt).
  update-desktop-database "$out/share/applications"
''
