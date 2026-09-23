#!/usr/bin/env python3
"""Compare fixture color palettes, not mismatched animation frames."""
import hashlib
import json
from pathlib import Path
from PIL import Image

root=Path(__file__).resolve().parent
result={'evidence_class':'offline analysis of native board captures',
        'limit':'Different animation frames; this is a region-palette comparison, not full pixel equivalence.',
        'captures':{},'differences':{}}
for mode in ('gpu','pixman'):
    result['captures'][mode]={}
    for name in ('scene-first','scene-later'):
        path=root/mode/(name+'.png')
        with Image.open(path) as source:
            im=source.convert('RGB')
            assert im.size==(568,1232)
            def palette(box):
                colors=im.crop(box).getcolors(568*1232)
                assert colors is not None
                return sorted([list(color) for _,color in colors],key=sum)
            parent=sum(1<<i for i in range(16) if im.getpixel((i*16+8,8))==(255,255,255))
            child=sum(1<<i for i in range(8) if im.getpixel((32+i*16+8,56))==(255,255,255))
            result['captures'][mode][name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'parent_counter_low16':parent,'child_counter_low8':child,
                'parent_palette':palette((0,144,568,1232)),
                'child_palette':palette((32,96,160,144))}
for region in ('parent_palette','child_palette'):
    gpu=result['captures']['gpu']['scene-first'][region]
    cpu=result['captures']['pixman']['scene-first'][region]
    assert len(gpu)==len(cpu)==2
    assert gpu==result['captures']['gpu']['scene-later'][region]
    assert cpu==result['captures']['pixman']['scene-later'][region]
    result['differences'][region]={'gpu_minus_pixman_rgb':[[g-c for g,c in zip(a,b)] for a,b in zip(gpu,cpu)],
                                  'equal':gpu==cpu}
result['status']='PASS' if all(v['equal'] for v in result['differences'].values()) else 'MISMATCH'
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['status']=='PASS' else 1)
