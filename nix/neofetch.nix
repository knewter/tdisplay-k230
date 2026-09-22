# Optional original Neofetch for the board; removed from the pinned Nixpkgs.
# Included with bring-up probes; also build directly with `nix build .#neofetch`.
{ stdenvNoCC, fetchurl, lib, bash, coreutils, gawk, gnugrep, gnused, procps }:
stdenvNoCC.mkDerivation {
  pname = "neofetch";
  version = "7.1.0";
  src = fetchurl {
    url = "https://raw.githubusercontent.com/dylanaraps/neofetch/7.1.0/neofetch";
    sha256 = "1is84fj3d4c0dwx9qkzrzja2i6lz784m459550aznaa0wn9k9hrx";
  };
  dontUnpack = true;
  installPhase = ''
    runHook preInstall
    mkdir -p $out/bin
    {
      printf '#!${bash}/bin/bash\n'
      printf 'export PATH="${lib.makeBinPath [ coreutils gawk gnugrep gnused procps ]}:$PATH"\n'
      tail -n +2 "$src"
    } > $out/bin/neofetch
    chmod +x $out/bin/neofetch
    runHook postInstall
  '';
  meta = {
    description = "Original Neofetch system information tool";
    license = lib.licenses.mit;
    mainProgram = "neofetch";
  };
}
