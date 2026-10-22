#!/usr/bin/env python3
"""Sample board CPU stacks during a workload and render flamegraphs.

Runs the opt-in `perf` (`nix build .#runtime-perf`, copied to the board) on
the main processes of the named systemd units while an optional workload
script runs on the board, then renders the samples on the host:

    tools/board-profile.py OUT_DIR --unit shell-ui --unit shell \\
        --workload drawer-scroll.py -- /var/tmp/drawer-prof SYSTEM 30

Without --workload it samples for --seconds. The board lock
(/tmp/k230-board.lock) is held for the whole capture. DWARF unwinding with a
64 KiB stack copy is the default: frame pointers stop in the nixpkgs C
libraries, and a 16 KiB copy truncates inside pixman's composite path.
Stock nixpkgs libraries keep `.symtab`, so names resolve without debug
packages.

OUT_DIR receives:

    perf-script.txt.gz  raw `perf script` text; open it in speedscope
                        (https://www.speedscope.app) for a time-ordered
                        flame chart per thread
    folded.txt          one line per unique stack, with sample counts
    flamegraph.svg      aggregated flamegraph (pinned FlameGraph scripts)
    summary.json        sampled CPU per process and the hottest frames
                        (inclusive and self share of sampled CPU)
    capture.log         unit PIDs (with start times), perf and workload
                        exit codes
    workload-out/       with --fetch, the workload's own board output

The output names processes, threads, functions and store paths; it holds no
addresses or journal text, so review it before committing like any capture.
"""
import argparse
import collections
import gzip
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SSH_CONFIG = Path.home() / 'tmp/k230-coordination/ssh_config.private'
BOARD_DIR = '/var/tmp/k230-profile'


def ssh(args, cmd, **kw):
    base = ['ssh', '-F', str(args.ssh_config), args.host]
    return subprocess.run(base + [cmd], check=True, **kw)


def board_tools(args):
    """The board's perf and python paths, found by store-path pattern."""
    script = (
        'ls -d /nix/store/*-perf-k230-runtime-*/bin/perf 2>/dev/null | head -1; '
        'ls -d /nix/store/*-python3-riscv64-*/bin/python3 2>/dev/null | head -1'
    )
    found = ssh(args, script, capture_output=True, text=True).stdout.split('\n')
    perf = args.perf or found[0].strip()
    python = args.python or (found[1].strip() if len(found) > 1 else '')
    if not perf:
        raise SystemExit('no runtime perf on the board; copy `nix build .#runtime-perf` there')
    return perf, python


def flamegraph_dir(args):
    if args.flamegraph:
        return Path(args.flamegraph)
    out = subprocess.run(
        ['nix', 'build', '--no-link', '--print-out-paths',
         '.#nixosConfigurations.k230.pkgs.buildPackages.flamegraph'],
        cwd=REPO, check=True, capture_output=True, text=True).stdout.split()[-1]
    return Path(out)


def remote_script(args, perf, python, workload_args):
    units = ' '.join(shlex.quote(u) for u in args.unit)
    record = (f'{shlex.quote(perf)} record -q -e cpu-clock -F {args.freq} '
              f'--call-graph dwarf,{args.stack} -o $D/perf.data -p "$PIDS"')
    if args.workload:
        run = (f'{record} & P=$!; sleep 1; '
               f'{shlex.quote(python)} $D/workload.py {workload_args} > $D/workload.log 2>&1 && W=0 || W=$?; '
               'kill -INT $P; wait $P && R=0 || R=$?; echo "workload_rc=$W perf_rc=$R"')
    else:
        run = f'{record} -- sleep {args.seconds}'
    return f'''set -e
D={BOARD_DIR}
PIDS=""
for u in {units}; do
  p=$(systemctl show -p MainPID --value "$u")
  [ "$p" != 0 ] || {{ echo "unit $u has no main process" >&2; exit 3; }}
  echo "pid $u $p $(cut -d' ' -f22 /proc/$p/stat) $(cat /proc/$p/comm)"
  PIDS="$PIDS${{PIDS:+,}}$p"
done
echo "start $(date -u +%Y-%m-%dT%H:%M:%SZ)"
{run}
echo "end $(date -u +%Y-%m-%dT%H:%M:%SZ)"
for u in {units}; do echo "pid-after $u $(systemctl show -p MainPID --value "$u")"; done
{shlex.quote(perf)} script -i $D/perf.data -F comm,pid,tid,time,period,event,ip,sym,dso 2>$D/script.err | gzip -1 > $D/perf-script.txt.gz
echo "script-warnings $(wc -l < $D/script.err)"
'''


def collapse(text_lines, fg):
    folded = subprocess.run(
        ['perl', str(fg / 'bin/stackcollapse-perf.pl'), '--all'],
        input=''.join(text_lines), check=True, capture_output=True, text=True).stdout
    return folded


def summarize(folded, top):
    inclusive, own = collections.Counter(), collections.Counter()
    per_comm, total = collections.Counter(), 0
    for line in folded.splitlines():
        stack, _, count = line.rpartition(' ')
        n = int(count)
        frames = stack.split(';')
        total += n
        per_comm[frames[0]] += n
        own[frames[-1]] += n
        for frame in set(frames[1:]):
            inclusive[frame] += n

    def ranked(counter):
        return [{'frame': f, 'cpu_ms': round(n / 1e6, 1), 'share': round(n / total, 4)}
                for f, n in counter.most_common(top)]
    # stackcollapse-perf weights each stack by its cpu-clock period (ns).
    return {'cpu_ms': round(total / 1e6, 1),
            'processes_cpu_ms': {c: round(n / 1e6, 1) for c, n in per_comm.most_common()},
            'inclusive': ranked(inclusive), 'self': ranked(own)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('out', type=Path)
    ap.add_argument('--unit', action='append', required=True,
                    help='systemd unit whose main process is sampled (repeatable)')
    ap.add_argument('--workload', type=Path, help='python script run as root on the board')
    ap.add_argument('--seconds', type=int, default=20, help='duration without a workload')
    ap.add_argument('--freq', type=int, default=199)
    ap.add_argument('--stack', type=int, default=65528, help='DWARF stack copy bytes')
    ap.add_argument('--fetch', help='board directory the workload writes; copied to OUT/workload-out and removed')
    ap.add_argument('--top', type=int, default=40)
    ap.add_argument('--title', default='k230 board CPU samples')
    ap.add_argument('--host', default='k230')
    ap.add_argument('--ssh-config', type=Path, default=SSH_CONFIG)
    ap.add_argument('--perf'); ap.add_argument('--python'); ap.add_argument('--flamegraph')
    ap.add_argument('workload_args', nargs='*')
    args = ap.parse_args()
    if not 5 <= args.seconds <= 180:
        raise SystemExit('--seconds must be 5-180')
    args.out.mkdir(parents=True)
    fg = flamegraph_dir(args)
    perf, python = board_tools(args)
    if args.workload and not python:
        raise SystemExit('no python on the board for the workload')

    ssh(args, f'rm -rf {BOARD_DIR} && mkdir -m 700 {BOARD_DIR}')
    if args.workload:
        ssh(args, f'cat > {BOARD_DIR}/workload.py', input=args.workload.read_bytes())
    workload_args = ' '.join(shlex.quote(a) for a in args.workload_args)
    script = remote_script(args, perf, python, workload_args)
    started = time.time()
    try:
        # perf exits 130 after the SIGINT that ends a workload capture.
        log = subprocess.run(['ssh', '-F', str(args.ssh_config), args.host,
                              f'flock -n /tmp/k230-board.lock sh -c {shlex.quote(script)}'],
                             capture_output=True, text=True, timeout=1800)
        (args.out / 'capture.log').write_text(log.stdout + log.stderr)
        if log.returncode:
            raise SystemExit(f'capture failed ({log.returncode}); see {args.out}/capture.log')
        data = ssh(args, f'cat {BOARD_DIR}/perf-script.txt.gz', capture_output=True).stdout
        if args.workload:
            wl = ssh(args, f'cat {BOARD_DIR}/workload.log', capture_output=True).stdout
            (args.out / 'workload.log').write_bytes(wl)
        if args.fetch:
            tar = ssh(args, f'tar -C {shlex.quote(args.fetch)} -cf - . && rm -rf {shlex.quote(args.fetch)}',
                      capture_output=True).stdout
            (args.out / 'workload-out').mkdir()
            subprocess.run(['tar', '-C', str(args.out / 'workload-out'), '-xf', '-'], input=tar, check=True)
    finally:
        ssh(args, f'rm -rf {BOARD_DIR}')
    (args.out / 'perf-script.txt.gz').write_bytes(data)
    pids = {}
    for line in log.stdout.splitlines():
        part = line.split()
        if part[0] == 'pid':
            pids[part[1]] = {'pid': int(part[2]), 'starttime': int(part[3]), 'comm': part[4]}
        elif part[0] == 'pid-after' and pids.get(part[1], {}).get('pid') != int(part[2]):
            print(f'warning: {part[1]} restarted during the capture', file=sys.stderr)

    folded = collapse(gzip.decompress(data).decode(errors='replace').splitlines(True), fg)
    (args.out / 'folded.txt').write_text(folded)
    svg = subprocess.run(
        ['perl', str(fg / 'bin/flamegraph.pl'), '--title', args.title, '--width', '1600'],
        input=folded, check=True, capture_output=True, text=True).stdout
    (args.out / 'flamegraph.svg').write_text(svg)
    summary = summarize(folded, args.top)
    summary.update({'units': pids, 'freq_hz': args.freq, 'call_graph': f'dwarf,{args.stack}',
                    'host_wall_s': round(time.time() - started, 1),
                    'capture': [l for l in log.stdout.splitlines() if not l.startswith('pid ')]})
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=1))
    print(f"{summary['cpu_ms']} ms sampled CPU {summary['processes_cpu_ms']} -> {args.out}/flamegraph.svg")
    for row in summary['inclusive'][:15]:
        print(f"  {row['share'] * 100:5.1f}%  {row['frame'][:110]}")


if __name__ == '__main__':
    main()
