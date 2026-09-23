#!/usr/bin/env python3
"""Read-only guard for the specific staged, recoverable RVV board trial."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

BASE = Path('/var/lib/k230/rvv-trial')
HELPER = '/nix/store/6sca423wcjlq1v9ynjpbv4ai48jf53l9-k230-root-growth/bin/k230-root-growth'


def sha(path, offset=0, length=None):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        f.seek(offset)
        while length is None or length:
            b=f.read(min(1024**2,length) if length is not None else 1024**2)
            if not b:
                assert not length, 'short read'
                break
            h.update(b)
            if length is not None:length-=len(b)
    return h.hexdigest()


def main():
    assert os.geteuid()==0 and len(sys.argv)==2
    token=sys.argv[1];assert re.fullmatch('[a-f0-9]{32}',token)
    m=json.loads((BASE/'manifest.json').read_text())
    normal=m['normal']
    assert os.path.realpath('/run/current-system')==normal['current_system']
    assert os.path.realpath('/nix/var/nix/profiles/system')==normal['current_system']
    g=json.loads(subprocess.check_output([HELPER],text=True))
    assert g['status']=='checked' and not g['mutation_requested']
    assert g['layout']==normal['guard']['layout']
    assert g['filesystem_bytes_before']==normal['guard']['filesystem_bytes_before']
    protected=normal['protected']
    assert sha(g['layout']['disk'],0,446)==protected['mbr_boot_code_sha256']
    assert sha(g['layout']['disk'],512,4*1024**2-512)==protected['firmware_gap_sha256']
    for name,expected in protected['boot_files_sha256'].items():
        assert sha('/boot/'+name)==expected,'normal boot file changed'
    for name,info in m['boot_files'].items():
        path=Path(m['kernel']) if name=='Image' else (Path('/boot')/name if name=='fw_jump_add_uboot_head.bin' else BASE/name)
        assert path.stat().st_size==info['bytes'] and sha(path)==info['sha256'],name+' differs from image'
    assert 'init='+m['system']+'/init' in (BASE/'bootargs.txt').read_text()
    paths=subprocess.check_output(['nix-store','-qR',m['system']],text=True).splitlines()
    assert len(paths)>600 and all(Path(p).exists() for p in paths)
    assert os.path.realpath('/nix/var/nix/gcroots/k230-rvv-board-trial')==m['system']
    assert subprocess.run(['systemctl','is-active','--quiet','shell']).returncode==0
    print('K230_RVV_READY '+token,flush=True)


if __name__=='__main__':main()
