#!/usr/bin/env python3
"""Host inspection of the SD image's MBR and extracted boot payload only."""
import argparse, hashlib, json, struct, subprocess, tempfile
from datetime import datetime, timezone
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--image', type=Path, required=True)
p.add_argument('--bundle', type=Path, required=True)
p.add_argument('--debugfs', type=Path, required=True)
p.add_argument('--scratch', type=Path, required=True)
a = p.parse_args()
def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while block := f.read(1024 * 1024): h.update(block)
    return h.hexdigest()
image = a.image.resolve(strict=True)
bundle = a.bundle.resolve(strict=True)
with image.open('rb') as f:
    mbr = f.read(512)
    assert mbr[510:512] == b'\x55\xaa'
    parts = []
    for i in range(4):
        e = mbr[446 + i * 16:462 + i * 16]
        if e[4]:
            start, count = struct.unpack_from('<II', e, 8)
            parts.append({'type': e[4], 'offset_bytes': start * 512, 'bytes': count * 512})
    assert len(parts) == 2 and all(x['type'] == 0x83 for x in parts)
    assert parts[0]['offset_bytes'] == 4 * 1024**2
    assert parts[0]['bytes'] == 112 * 1024**2
    assert parts[1]['offset_bytes'] == 128 * 1024**2
    assert parts[1]['offset_bytes'] + parts[1]['bytes'] <= image.stat().st_size
    with tempfile.TemporaryDirectory(prefix='k230-image-inspect-', dir=a.scratch) as temp:
        temp = Path(temp)
        boot = temp / 'boot.ext4'
        f.seek(parts[0]['offset_bytes'])
        with boot.open('wb') as out:
            remaining = parts[0]['bytes']
            while remaining:
                block = f.read(min(remaining, 1024 * 1024)); assert block
                out.write(block); remaining -= len(block)
        observed = {}
        for name in ['Image', 'k230-tdisplay.dtb', 'initrd.uimg', 'bootargs.txt', 'force_dtb', 'lcd_dtb', 'hdmi_dtb']:
            target = temp / name
            subprocess.run([str(a.debugfs), '-R', f'dump /{name} {target}', str(boot)], check=True, capture_output=True)
            assert target.is_file(), name
            observed[name] = {'sha256': sha(target), 'bytes': target.stat().st_size}
            if name in ['force_dtb', 'lcd_dtb', 'hdmi_dtb']:
                assert target.read_bytes() == b'k230-tdisplay.dtb', name
            else:
                assert target.read_bytes() == (bundle / name).read_bytes(), name
print(json.dumps({
    'recorded_at': datetime.now(timezone.utc).isoformat(),
    'evidence_class': 'host-built SD image, MBR and extracted boot payload',
    'command': 'python3 docs/evidence/hdmi-hotplug/live-switch/inspect-sd-image.py --image <sdImage> --bundle <matching-trial-bundle> --debugfs <pinned-debugfs> --scratch <private-scratch>',
    'image': str(image), 'image_bytes': image.stat().st_size, 'image_sha256': sha(image),
    'bundle': str(bundle), 'identity': json.loads((bundle / 'identity.json').read_text()),
    'partitions': parts, 'boot_payload': observed,
    'kernel_tree_initrd_and_bootargs_match_trial_bundle': True,
    'all_selectors_name_combined_tree': True, 'result': 'PASS',
    'limits': ['Host boot-payload inspection only; not a flashed-image, untouched autoboot or physical glass/input result.', 'The root partition layout is checked; its filesystem contents are not independently extracted by this recipe.'],
}, indent=2))
