{ callPackage, writeShellApplication, python3, util-linux, e2fsprogs, coreutils }:
writeShellApplication {
  name = "k230-root-growth-guest";
  runtimeInputs = [ python3 util-linux e2fsprogs coreutils (callPackage ./growpart.nix { }) ];
  text = ''exec python3 ${../tests/root_growth_guest.py} --helper ${../tools/root-growth.py}'';
}
