#!/usr/bin/env python3
"""Build and publish a source-pinned coherent/vendor-kernel development image."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import lzma
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import quote

REPO = Path(__file__).resolve().parents[1]
TARGETS = {
    'image': 'packages.x86_64-linux.sdImage-coherent',
    'system': 'nixosConfigurations.k230-coherent-shell.config.system.build.toplevel',
    'kernel': 'nixosConfigurations.k230-coherent-shell.config.boot.kernelPackages.kernel',
    'device_tree': 'packages.x86_64-linux.deviceTree',
}
LIMITS = ('Host cross-build and uploaded-byte checks only. This exact full image has '
          'not been flashed or accepted on physical hardware and has no QEMU boot proof. '
          'Fresh-image startup/Home physical acceptance must be established separately.')


def run(args, *, capture=True, cwd=REPO):
    result = subprocess.run([str(x) for x in args], cwd=cwd, check=True,
                            stdout=subprocess.PIPE if capture else None, text=True)
    return result.stdout.strip() if capture else None


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def clean_source():
    if run(['git', 'status', '--porcelain', '--untracked-files=no']):
        raise ValueError('Tracked source is dirty; commit or resolve owned edits first')


def revision_sha(revision):
    sha = run(['git', 'rev-parse', '--verify', revision + '^{commit}'])
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('Expected a full Git commit SHA')
    return sha


def outside_git(directory):
    directory = Path(directory).expanduser().resolve()
    # Reject paths inside any Git checkout, including a different worktree.
    probe = directory
    while not probe.exists():
        probe = probe.parent
    if subprocess.run(['git', '-C', str(probe), 'rev-parse', '--show-toplevel'],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        raise ValueError('Asset directory must be outside every Git checkout')
    return directory


def flake(revision):
    return 'git+file://' + quote(str(REPO), safe='/') + '?rev=' + revision


def evaluate(revision):
    source = flake(revision)
    outputs = {}
    for name, attr in TARGETS.items():
        outputs[name] = {field: run(['nix', 'eval', '--raw', '--no-write-lock-file',
                                    source + '#' + attr + '.' + field])
                         for field in ('outPath', 'drvPath')}
    return outputs


def notes(metadata):
    return (f"Development snapshot of the coherent Rust handheld shell with the normal "
            f"vendor Xuantie kernel {metadata['kernel_version']}.\n\n"
            f"Source: `{metadata['revision']}`\n"
            f"Target: `sdImage-coherent` / `k230-coherent-shell`\n"
            f"System: `{metadata['outputs']['system']['outPath']}`\n"
            f"Kernel: `{metadata['outputs']['kernel']['outPath']}`\n\n"
            f"Validation: {LIMITS}\n\n"
            f"{metadata.get('operator_note', '')}\n\n"
            "Download the `.img.xz`, `SHA256SUMS` and `release-metadata.json`. "
            "Run `sha256sum -c SHA256SUMS` in the download directory, then "
            "`xz -d <image>.img.xz` to obtain the raw SD image. "
            "Mainline, SMP and RVV trial image targets are excluded.\n")


def write_checksums(directory, assets):
    (directory / 'SHA256SUMS').write_text(''.join(
        f'{digest(directory / name)}  {name}\n' for name in assets))


def stage(args):
    clean_source()
    revision = revision_sha(args.revision)
    tag = args.tag or 'dev-coherent-' + revision[:12]
    run(['git', 'check-ref-format', 'refs/tags/' + tag])
    directory = outside_git(args.directory or Path.home() / 'tmp' / ('k230-release-' + revision[:12]))
    directory.mkdir(parents=True, exist_ok=False)
    roots = directory / 'gc-roots'
    roots.mkdir()
    outputs = evaluate(revision)
    commands = []
    for name, attr in TARGETS.items():
        cmd = ['nix', 'build', '--no-write-lock-file', flake(revision) + '#' + attr,
               '--out-link', str(roots / name), '--max-jobs', '1', '--cores', '8']
        commands.append(cmd)
        print('Building ' + name, flush=True)
        run(cmd, capture=False)
        if str((roots / name).resolve()) != outputs[name]['outPath']:
            raise ValueError('Build output differs from pinned evaluation')
    image = Path(outputs['image']['outPath'])
    if not image.is_file():
        raise ValueError('Expected a raw image file output')
    image_name = f'tdisplay-k230-coherent-{revision[:12]}.img.xz'
    print('Compressing image', flush=True)
    with (directory / image_name).open('wb') as target:
        subprocess.run(['xz', '-T8', '-3', '--stdout', str(image)], stdout=target, check=True)
    metadata = {'schema': 1, 'revision': revision, 'tag': tag, 'repository': args.repository,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'target': 'sdImage-coherent', 'configuration': 'k230-coherent-shell',
                'kernel_version': run(['nix', 'eval', '--raw', '--no-write-lock-file',
                     flake(revision) + '#' + TARGETS['kernel'] + '.version']),
                'flake_lock_sha256': hashlib.sha256(subprocess.check_output(
                    ['git', 'show', revision + ':flake.lock'], cwd=REPO)).hexdigest(),
                'operator_note': args.validation_note or '',
                'outputs': outputs, 'build_commands': commands, 'validation_limits': LIMITS,
                'image': {'name': image_name, 'sha256': digest(image), 'bytes': image.stat().st_size},
                'compressed': {'sha256': digest(directory / image_name),
                               'bytes': (directory / image_name).stat().st_size}}
    (directory / 'release-metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (directory / 'release-notes.md').write_text(notes(metadata))
    write_checksums(directory, [image_name, 'release-metadata.json', 'release-notes.md'])
    print(directory)


def verify_stage(directory, metadata):
    if revision_sha(metadata['revision']) != metadata['revision']:
        raise ValueError('Staged revision is not an exact commit SHA')
    if metadata['target'] != 'sdImage-coherent' or metadata['configuration'] != 'k230-coherent-shell':
        raise ValueError('Unsupported image selection')
    if evaluate(metadata['revision']) != metadata['outputs']:
        raise ValueError('Provenance differs from pinned source evaluation')
    if (directory / 'release-notes.md').read_text() != notes(metadata) or metadata['validation_limits'] != LIMITS:
        raise ValueError('Validation limits or release notes do not match')
    expected = {metadata['image']['name'], 'release-metadata.json', 'release-notes.md'}
    checks = {}
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        sha, name = line.split('  ', 1)
        if name not in expected or name in checks or not re.fullmatch('[a-f0-9]{64}', sha):
            raise ValueError('Unexpected checksum entry')
        checks[name] = sha
    if set(checks) != expected:
        raise ValueError('Missing asset checksum')
    for name, sha in checks.items():
        if digest(directory / name) != sha:
            raise ValueError('Asset checksum mismatch: ' + name)
    compressed = directory / metadata['image']['name']
    if digest(compressed) != metadata['compressed']['sha256'] or compressed.stat().st_size != metadata['compressed']['bytes']:
        raise ValueError('Compressed image differs from metadata')
    print('Verifying decompressed image', flush=True)
    h = hashlib.sha256(); size = 0
    with lzma.open(compressed, 'rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block); size += len(block)
    if h.hexdigest() != metadata['image']['sha256'] or size != metadata['image']['bytes']:
        raise ValueError('Decompressed image differs from metadata')
    if digest(metadata['outputs']['image']['outPath']) != metadata['image']['sha256']:
        raise ValueError('Image differs from pinned build output')
    return [*sorted(expected), 'SHA256SUMS']


def fresh_release(repository, tag):
    # Listing both releases and tags fails closed on authentication/network errors.
    for endpoint, field in [('releases', 'tag_name'), ('tags', 'name')]:
        values = json.loads(run(['gh', 'api', '--paginate', '--slurp', f'repos/{repository}/{endpoint}']))
        if any(item[field] == tag for page in values for item in page):
            raise ValueError('Release or tag already exists: ' + tag)


def publish(args):
    clean_source()
    directory = outside_git(args.directory)
    metadata = json.loads((directory / 'release-metadata.json').read_text())
    assets = verify_stage(directory, metadata)
    repo, tag = metadata['repository'], metadata['tag']
    run(['git', 'check-ref-format', 'refs/tags/' + tag])
    fresh_release(repo, tag)
    remote_commit = json.loads(run(['gh', 'api', f'repos/{repo}/commits/{metadata["revision"]}']))
    if remote_commit['sha'] != metadata['revision']:
        raise ValueError('Source commit unavailable on GitHub')
    run(['gh', 'release', 'create', tag, '--repo', repo, '--target', metadata['revision'],
         '--draft', '--prerelease', '--title', 'Coherent handheld development snapshot ' + metadata['revision'][:12],
         '--notes-file', str(directory / 'release-notes.md'), *[str(directory / x) for x in assets]], capture=False)
    # A failed verification leaves a draft; never edits/replaces earlier releases.
    info = json.loads(run(['gh', 'api', f'repos/{repo}/releases/tags/{quote(tag, safe="")}']))
    if {x['name'] for x in info['assets']} != set(assets):
        raise ValueError('Remote assets differ; release remains draft')
    with tempfile.TemporaryDirectory(prefix='verify-', dir=directory) as temp:
        run(['gh', 'release', 'download', tag, '--repo', repo, '--dir', temp], capture=False)
        for asset in info['assets']:
            name = asset['name']
            if asset['size'] != (directory / name).stat().st_size or digest(Path(temp) / name) != digest(directory / name):
                raise ValueError('Remote asset mismatch; release remains draft: ' + name)
    run(['gh', 'release', 'edit', tag, '--repo', repo, '--draft=false'], capture=False)
    info = json.loads(run(['gh', 'api', f'repos/{repo}/releases/tags/{quote(tag, safe="")}']))
    if info['draft'] or not info['prerelease']:
        raise ValueError('Release publication state differs')
    report = {'url': info['html_url'], 'revision': metadata['revision'], 'tag': tag,
              'published_at': info['published_at'], 'assets': [
                  {'name': a['name'], 'bytes': a['size'], 'sha256': digest(directory / a['name']),
                   'url': a['browser_download_url']} for a in info['assets']]}
    (directory / 'publication.json').write_text(json.dumps(report, indent=2) + '\n')
    print(info['html_url'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('stage', help='Build a pinned image and stage assets outside Git')
    build.add_argument('--revision', default='master')
    build.add_argument('--directory')
    build.add_argument('--repository', default='knewter/tdisplay-k230')
    build.add_argument('--tag')
    build.add_argument('--validation-note', help='Additional observed context; cannot replace mandatory limits')
    publish_parser = sub.add_parser('publish', help='Verify assets, create and publish a fresh prerelease')
    publish_parser.add_argument('--directory', required=True)
    args = parser.parse_args()
    try:
        (stage if args.command == 'stage' else publish)(args)
    except (ValueError, OSError, subprocess.CalledProcessError, lzma.LZMAError) as error:
        parser.exit(1, f'Error: {error}\n')


if __name__ == '__main__':
    main()
