let
  paths = builtins.map builtins.storePath
    (builtins.fromJSON (builtins.readFile ./extra-inputs.json));
  manifest = builtins.toFile "k230-retained-combined-paths"
    (builtins.concatStringsSep "\n" paths + "\n");
  bash = builtins.storePath "/nix/store/svx59425zxp552p2b8gm11qj5r09b56i-bash-5.3p15";
  coreutils = builtins.storePath "/nix/store/xjl7p8dvyk2j53kqf7f43kdj4ypbxz7g-coreutils-9.11";
in builtins.derivation {
  name = "tdisplay-k230-retained-coherent-combined-build-inputs";
  system = "x86_64-linux";
  builder = "${bash}/bin/bash";
  args = [ "-e" "-c" ''
    ${coreutils}/bin/mkdir "$out"
    index=0
    while IFS= read -r path; do
      printf -v entry 'path-%05d' "$index"
      ${coreutils}/bin/ln -s "$path" "$out/$entry"
      index=$((index + 1))
    done < ${manifest}
  '' ];
}
