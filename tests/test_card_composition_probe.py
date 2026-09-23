#!/usr/bin/env python3
"""Executable host policy gates plus opt-in packaging checks.

These tests execute the compositor's real C gesture policy. Cross-building
pins the scene ABI; hardware lifecycle/focus remains an explicit board gate.
"""
from pathlib import Path
import argparse
import os
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--mode',choices=['selected'])
 p.add_argument('--sway',default=os.environ.get('K230_CARD_TEST_SWAY'))
 p.add_argument('--client',default=os.environ.get('K230_CARD_TEST_CLIENT'))
 p.add_argument('--case',action='append',choices=['two-app-drag','stale-destroy','disabled','select','close-refused','app-exit','keyboard-return'])
 args=p.parse_args()
 with tempfile.TemporaryDirectory(prefix='card-policy-') as tmp:
  exe=Path(tmp)/'policy'
  subprocess.run([os.environ.get('CC','cc'),'-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-o',str(exe),str(ROOT/'tests/card_composition_policy.c'),'-lm'],check=True)
  subprocess.run([str(exe)],check=True)
 package=(ROOT/'nix/card-composition-probe.nix').read_text()
 source=(ROOT/'nix/card-composition-probe/card.c').read_text()
 shell=(ROOT/'nix/shell.nix').read_text()
 assert 'sway-unwrapped = patchedUnwrapped' in package
 assert 'export WLR_RENDERER=pixman' in package
 assert '/dev/dri' not in package+source
 assert 'card-composition-probe' not in shell
 print('PASS opt-in package isolation; physical keyboard remains a board gate')
 if args.case:
  if not args.sway or not args.client:
   p.error('runtime cases require --sway/--client or K230_CARD_TEST_SWAY/K230_CARD_TEST_CLIENT; policy alone does not prove scene lifetime')
  runtime=['python3',str(ROOT/'tests/card_composition_headless.py'),'--sway',args.sway,'--client',args.client]
  subprocess.run(runtime,check=True)
  if 'disabled' in args.case: subprocess.run(runtime+['--disabled'],check=True)
 return 0
if __name__=='__main__': raise SystemExit(main())
