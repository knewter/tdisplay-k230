# Why stage 1 dropped to emergency mode, and why the DTB could not fix it

Observed on hardware. The initrd ran, mounted the root filesystem, and then
failed anyway:

```
[  OK  ] Finished Create Volatile Files and Directories in the Real Root.
You are in emergency mode. ...
Cannot open access to console, the root account is locked.
```

Two facts are visible in those three lines:

- The root filesystem **is** mounted. "in the Real Root" is the `/sysroot`
  variant of the tmpfiles unit; it cannot run before `sysroot.mount`.
- The failing unit ordered immediately after it, and it is fatal to
  `initrd.target`.

## The failing unit

`initrd-find-nixos-closure.service`, from
`nixos/modules/system/boot/systemd/initrd.nix`:

```bash
closure=
for o in $(< /proc/cmdline); do
    case $o in
        init=*) ... closure="${initParam[1]}" ;;
    esac
done

if [ -z "${closure:-}" ]; then
  echo 'No init= parameter on the kernel command line' >&2
  exit 1
fi
```

It is declared `RequiresMountsFor = "/sysroot/nix/store"` (hence running right
after the sysroot tmpfiles unit) and `requiredBy = [ "initrd.target" ]` — so
`exit 1` fails `initrd.target`, which is emergency mode. `sulogin` then cannot
offer a prompt because NixOS leaves root locked, which is why the boot stops
dead rather than dropping to a shell.

So the whole failure reduces to: **`init=` was not on the kernel command line.**

## Why writing it into the DTB was not enough

`nix/sd-image.nix` does `fdtput -t s ... /chosen bootargs`, and that is genuinely
required — an earlier boot with no `/chosen/bootargs` at all was silent on both
UARTs. But it is overwritten. `board/canaan/common/k230_img.c:110`:

```c
char *board_fdt_chosen_bootargs(void){
    char *bootargs = env_get("bootargs");
    if(NULL == bootargs) {
        ...
        bootargs = "root=/dev/mmcblk1p2 loglevel=8 rw rootdelay=4 rootfstype=ext4 console=ttyS0,115200  earlycon=sbi";
    }
    printf("g_bootmod = %d, bootargs=%s\n", g_bootmod, bootargs);
    return bootargs;
}
```

The vendor environment never defines `bootargs`, so U-Boot took the fallback
branch and replaced `/chosen/bootargs` with that hardcoded string. The
`g_bootmod = 3` line seen on every boot is line 126 of this function.

This also explains a coincidence worth naming: the boot got as far as it did
**because** that fallback string happens to carry `root=/dev/mmcblk1p2`, which
matches our partition layout. The root mount that appeared to work was the
vendor's doing, not ours.

## The fix

`env_get("bootargs")` is checked first, so defining it wins outright. The
command line names the NixOS closure and therefore changes on every rebuild,
while the stage 1 environment image must not — so the value is not baked into
`env.env`. Instead `blinux` loads it from the boot partition:

```
blinux=k230_set_dtb
  && ext4load mmc ${mmc_boot_dev_num}:1 0x7000000 /bootargs.txt
  && env import -t 0x7000000 ${filesize}
  && ...
```

- `CONFIG_CMD_IMPORTENV=y` in this U-Boot build.
- `ext4load` sets `filesize` (`fs/fs.c:743`), consumed by the next command.
- `0x7000000` is above the ~60 MB kernel at `0x200000` and below fw_jump at
  `0x8000000`.

`nix/sd-image.nix` writes `bootargs.txt` from `config.boot.kernelParams` plus
`init=`, the same string it puts in the DTB, so the two cannot disagree.

## What this does not yet prove

`root=fstab` (set by nixpkgs' systemd-initrd module) resolves the root device
through the initrd's fstab, i.e. `/dev/disk/by-label/NIXOS_SD`. Because the
vendor fallback supplied an explicit `root=` until now, **the by-label path has
never actually been exercised on this board.** If sysroot fails to mount on the
next boot, that is the thing to suspect, not the `init=` fix.
