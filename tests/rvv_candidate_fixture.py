"""Temporary candidate tree for host-only guard tests."""
import json
from pathlib import Path


def candidate(root, identity):
    paths = {key: str(root / key) for key in identity.PATHS}
    for key in ('system', 'kernel', 'pixel_probe', 'card_package'):
        Path(paths[key]).mkdir()
    files = {key: identity.file_for(paths, key) for key in identity.FILES}
    for key, path in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('built candidate ' + key)
    (Path(paths['system']) / 'boot.json').write_text(json.dumps({
        'org.nixos.bootspec.v1': {
            'kernel': str(files['kernel_image']), 'toplevel': paths['system']}}))
    manifest = {'schema': identity.SCHEMA, **paths,
                'sha256': {key: identity.digest(path) for key, path in files.items()}}
    path = root / 'candidate.json'
    path.write_text(json.dumps(manifest))
    return path, manifest
