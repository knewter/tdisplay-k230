{ writeShellApplication, runtimeShell, cloud-utils, coreutils, gnugrep, gnused, gawk, util-linux }:
# The pinned script alone; cloud-utils.guest also builds its sibling output's
# qemu-utils/CD-image programs, which this guarded DOS-layout operation never uses.
writeShellApplication {
  name = "growpart";
  runtimeInputs = [ coreutils gnugrep gnused gawk util-linux ];
  text = ''exec ${runtimeShell} ${cloud-utils.src}/bin/growpart "$@"'';
}
