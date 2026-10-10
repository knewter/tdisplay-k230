let f = builtins.getFlake "/home/jadams/tmp/k230-coherent-closeout-2026-10-10";
    p = f.inputs.nixpkgs.legacyPackages.x86_64-linux;
    paths = builtins.fromJSON (builtins.readFile ./build-inputs.json);
in p.linkFarm "tdisplay-k230-retained-coherent-help-build-inputs"
  (builtins.map (entry: { inherit (entry) name; path = builtins.storePath entry.path; }) paths)
