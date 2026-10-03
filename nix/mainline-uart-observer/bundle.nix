# Add a checked observer inventory to the usual matching trial artifacts.
{ runCommand, dtc, lib, trial, baseBundle, kernel, system, helper }:
runCommand "k230-mainline-uart-observer-boot-files" {
  nativeBuildInputs = [ dtc ];
} ''
  mkdir -p $out
  cp -a ${trial}/. $out/
  chmod u+w $out
  chmod +w $out/SHA256SUMS
  test '${kernel}' = "$(dirname "$(readlink -f ${baseBundle}/system/kernel)")"
  cmp $out/Image-mainline-drm ${baseBundle}/Image-mainline-drm
  cp $out/k230-tdisplay-mainline-drm.dtb selected.dtb
  cp ${baseBundle}/k230-tdisplay-mainline-drm.dtb base.dtb
  chmod +w selected.dtb base.dtb
  fdtput -d selected.dtb /chosen bootargs
  fdtput -d base.dtb /chosen bootargs
  dtc -s -I dtb -O dts selected.dtb > selected.dts
  dtc -s -I dtb -O dts base.dtb > base.dts
  cmp selected.dts base.dts
  helper_sha=$(sha256sum ${helper}/bin/k230-uart-observer | cut -d' ' -f1)
  dtb_sha=$(sha256sum $out/k230-tdisplay-mainline-drm.dtb | cut -d' ' -f1)
  base_dtb_sha=$(sha256sum ${baseBundle}/k230-tdisplay-mainline-drm.dtb | cut -d' ' -f1)
  cat > $out/observer.json <<JSON
  {
    "schema": "k230-uart-observer-artifact-v1",
    "protocol": "K230_UOBS_V1",
    "helper": "${helper}/bin/k230-uart-observer",
    "helper_sha256": "$helper_sha",
    "helper_source_sha256": "${builtins.hashFile "sha256" ./observer.c}",
    "system": "${system}",
    "init": "${system}/init",
    "kernel": "${kernel}",
    "base_kernel": "${kernel}",
    "base_bundle": "${baseBundle}",
    "dtb_sha256": "$dtb_sha",
    "base_dtb_sha256": "$base_dtb_sha",
    "dtb_bootargs_only": true,
    "window_ms": 12000,
    "payload_max": 384
  }
JSON
  cd $out
  sha256sum observer.json >> SHA256SUMS
''
