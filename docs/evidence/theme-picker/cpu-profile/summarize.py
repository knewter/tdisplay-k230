"""Reproduce reviewed artifacts from private thread-aware collapsed perf output.

This trial has exactly 697 samples with uniform 10,101,010 ns periods. Reject
other captures instead of accidentally interpreting sample weights as counts.
"""
import collections
import hashlib
import json
from pathlib import Path
import re
import sys

source, destination = Path(sys.argv[1]), Path(sys.argv[2])
stacks, leaves, flat, processes = (collections.Counter() for _ in range(4))
unknown = leaf_unknown = redacted = capped = 0
for line in source.read_text().splitlines():
    stack, weight = line.rsplit(' ', 1)
    count, remainder = divmod(int(weight), 10101010)
    assert not remainder and count > 0
    parts = stack.split(';')
    assert re.fullmatch(r'[A-Za-z0-9_().-]+-\d+/\d+', parts[0])
    for i, frame in enumerate(parts[1:], 1):
        if '/' in frame or re.search(r'0x[0-9a-fA-F]+', frame) or re.fullmatch(r'[0-9a-fA-F]{8,}', frame):
            parts[i] = '[unresolved]'
            redacted += 1
    if any('unknown' in f or 'unresolved' in f for f in parts[1:]):
        unknown += count
    if 'unknown' in parts[-1] or 'unresolved' in parts[-1]:
        leaf_unknown += count
    if len(parts) >= 128:
        capped += count
    stacks[';'.join(parts)] += count
    flat[';'.join([parts[0], parts[-1]])] += count
    leaves[parts[-1]] += count
    processes[parts[0]] += count
assert sum(stacks.values()) == 697
for name, values in [('stacks.folded', stacks), ('hotspots.folded', flat)]:
    (destination / name).write_text(''.join(k+' '+str(v)+'\n' for k,v in sorted(values.items())))
quality = dict(schema=1, samples=697, uniform_period_ns=10101010,
               source_folded_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
               unknown_caller_samples=unknown, unknown_leaf_samples=leaf_unknown,
               at_or_beyond_128_entries=capped, redacted_frames=redacted,
               samples_by_thread=dict(processes.most_common()),
               top_leaf_symbols=[dict(symbol=k,samples=v) for k,v in leaves.most_common(20)],
               limits=['Caller chains include unresolved frames and reach the depth cap.',
                       'Leaf PCs resolved; complete caller attribution still needs qualification.',
                       'Uniform periods allow conversion of collapsed nanosecond weights into sample counts.',
                       'This trial includes route opening, helper descendants, and four injected swipes.',
                       'Separate workload from the earlier trace, without matched observer-overhead control.'])
(destination / 'stack-quality.json').write_text(json.dumps(quality,indent=2)+'\n')
