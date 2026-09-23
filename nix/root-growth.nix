{ callPackage, writeShellApplication, python3, util-linux, e2fsprogs }:
writeShellApplication {
  name = "k230-root-growth";
  runtimeInputs = [ python3 util-linux e2fsprogs (callPackage ./growpart.nix { }) ];
  text = ''exec python3 ${../tools/root-growth.py} "$@"'';
}
