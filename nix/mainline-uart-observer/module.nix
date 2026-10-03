# Opt-in initrd-only reporter. Nonce/normal boot/init identity are volatile,
# supplied by the reviewed host controller, avoiding a toplevel/initrd cycle.
{ config, lib, pkgs, ... }:
let
  helper = pkgs.callPackage ./default.nix {
    systemd = config.boot.initrd.systemd.package;
  };
in {
  boot.initrd.systemd = {
    storePaths = [ helper ];
    contents."/etc/k230-uobs-version".text = "1\n";
    services.debug-shell = {
      overrideStrategy = "asDropin";
      # The debug generator alone selects/starts this service. A missing
      # identity token must not create a repeated or unconditional reporter.
      unitConfig.ConditionKernelCommandLine = "k230.uobs.nonce";
      serviceConfig = {
        ExecStart = lib.mkForce [ "" "${helper}/bin/k230-uart-observer" ];
        Restart = lib.mkForce "no";
      };
    };
  };
}
