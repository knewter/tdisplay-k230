"""Read a built sdImage without mounting or writing: list its boot ext4.

usage: inspect-image.py <image> <expected-system-init-or-empty>
The boot partition is located with sfdisk (partition 1), copied out with
dd-style reads, and queried with debugfs. No root is needed.
"""
import hashlib, json, subprocess, sys, tempfile
from pathlib import Path

image = Path(sys.argv[1]).resolve()
table = json.loads(subprocess.run(["sfdisk", "--json", str(image)],
                   capture_output=True, text=True, check=True).stdout)
part = table["partitiontable"]["partitions"][0]
sector = table["partitiontable"].get("sectorsize", 512)
offset, length = part["start"] * sector, part["size"] * sector
with image.open("rb") as src:
    digest = hashlib.file_digest(src, "sha256").hexdigest()
    src.seek(offset)
    data = src.read(length)
with tempfile.NamedTemporaryFile(suffix=".ext4") as boot:
    boot.write(data); boot.flush()
    def q(cmd):
        r = subprocess.run(["debugfs", "-R", cmd, boot.name],
                           capture_output=True, text=True, check=True)
        return r.stdout + r.stderr
    listing, bootargs, logo = q("ls -l /"), q("cat /bootargs.txt"), q("stat /logo.xrgb")
assert "Image" in listing and "initrd.uimg" in listing
assert "logo.xrgb" not in listing and "File not found" in logo
assert "console=tty0" in bootargs
print(json.dumps({"image": str(image), "bytes": image.stat().st_size,
    "sha256": digest, "partitionOffsetBytes": offset,
    "partitionLengthBytes": length, "partitionType": part.get("type"),
    "listing": listing, "bootargs": bootargs, "logoStat": logo,
    "result": "PASS: boot partition omits logo.xrgb and bootargs carry console=tty0"},
    indent=2))
