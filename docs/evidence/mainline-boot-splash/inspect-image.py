"""Read a built sdImage without mounting or writing: list its boot ext4.

Adapted from docs/evidence/splash-close-sdimage/inspect-image.py, which
asserts the opposite (no logo, console=tty0). This one expects the splash
build: /logo.xrgb present at exactly 2799104 bytes, no console=tty0 in
bootargs.txt, and the DTB on the partition carrying the splash reservation.

usage: inspect-image.py <image> <fdtget-binary>
No root is needed; debugfs and fdtget only read.
"""
import hashlib, json, re, subprocess, sys, tempfile
from pathlib import Path

LOGO_BYTES = 2799104
image = Path(sys.argv[1]).resolve()
fdtget = sys.argv[2]
table = json.loads(subprocess.run(["sfdisk", "--json", str(image)],
                   capture_output=True, text=True, check=True).stdout)
part = table["partitiontable"]["partitions"][0]
sector = table["partitiontable"].get("sectorsize", 512)
offset, length = part["start"] * sector, part["size"] * sector
with image.open("rb") as src:
    digest = hashlib.file_digest(src, "sha256").hexdigest()
    src.seek(offset)
    data = src.read(length)
with tempfile.TemporaryDirectory() as tmp:
    boot = Path(tmp) / "boot.ext4"
    boot.write_bytes(data)
    def q(cmd):
        r = subprocess.run(["debugfs", "-R", cmd, str(boot)],
                           capture_output=True, text=True, check=True)
        return r.stdout + r.stderr
    listing, bootargs, logo = q("ls -l /"), q("cat /bootargs.txt"), q("stat /logo.xrgb")
    logo_dump = Path(tmp) / "logo.xrgb"
    q(f"dump /logo.xrgb {logo_dump}")
    logo_size = logo_dump.stat().st_size if logo_dump.exists() else None
    logo_sha = hashlib.sha256(logo_dump.read_bytes()).hexdigest() if logo_size else None
    dtb = Path(tmp) / "k230-tdisplay.dtb"
    q(f"dump /k230-tdisplay.dtb {dtb}")
    def fget(*a):
        return subprocess.run([fdtget, str(dtb), *a], capture_output=True,
                              text=True, check=True).stdout.strip()
    reserved = {"nodes": fget("-l", "/reserved-memory").split(),
                "reg": fget("-t", "x", "/reserved-memory/framebuffer@10000000", "reg"),
                "properties": fget("-p", "/reserved-memory/framebuffer@10000000").split()}
assert "Image" in listing and "initrd.uimg" in listing and "logo.xrgb" in listing
assert logo_size == LOGO_BYTES, logo_size
assert "console=tty0" not in bootargs
assert reserved["reg"].split() == ["0", "10000000", "0", "400000"], reserved
assert "no-map" in reserved["properties"], reserved
print(json.dumps({"image": str(image), "bytes": image.stat().st_size,
    "sha256": digest, "partitionOffsetBytes": offset,
    "partitionLengthBytes": length, "partitionType": part.get("type"),
    "listing": listing, "bootargs": bootargs, "logoStat": logo,
    "logoBytes": logo_size, "logoSha256": logo_sha,
    "dtbReservedMemory": reserved,
    "result": "PASS: boot partition carries logo.xrgb (2799104 bytes), bootargs omit console=tty0, DTB reserves 0x10000000+0x400000 no-map"},
    indent=2))
