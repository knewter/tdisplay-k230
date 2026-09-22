"""Read the current console image without mounting or writing to it."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

base = Path(__file__).resolve().parent
evaluation = json.loads((base / "both-states.json").read_text())
image = Path(evaluation["consoleImage"]["imagePath"])
with image.open("rb") as source:
    digest = hashlib.file_digest(source, "sha256").hexdigest()
    source.seek(4 * 1024 * 1024)
    partition = source.read(112 * 1024 * 1024)
assert len(partition) == 112 * 1024 * 1024
with tempfile.NamedTemporaryFile(suffix=".ext4") as boot:
    boot.write(partition)
    boot.flush()
    def query(command):
        result = subprocess.run(
            ["debugfs", "-R", command, boot.name],
            capture_output=True, text=True, check=True,
        )
        return result.stdout + result.stderr
    listing = query("ls -l /")
    bootargs = query("cat /bootargs.txt")
    logo_stat = query("stat /logo.xrgb")
assert "Image" in listing and "initrd.uimg" in listing
assert "logo.xrgb" not in listing
assert "File not found" in logo_stat
assert "console=tty0" in bootargs
assert evaluation["console"]["systemPath"] + "/init" in bootargs
report = {
    "image": str(image), "bytes": image.stat().st_size, "sha256": digest,
    "partitionOffsetBytes": 4 * 1024 * 1024,
    "partitionLengthBytes": len(partition),
    "listing": listing, "bootargs": bootargs, "logoStat": logo_stat,
    "result": "PASS: console image omits logo and selects console=tty0",
}
print(json.dumps(report, indent=2))
