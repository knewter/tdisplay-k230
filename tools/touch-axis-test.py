#!/usr/bin/env python3
"""Decide whether the touchscreen axes are swapped or mirrored.

The question "are the axes right" cannot be answered by a drag alone: a
drag proves the coordinates move, not that they move the right way. It
needs a touch at a *known* position on the glass, which means drawing a
target and seeing what the controller reports for it.

So this draws four 180 px corner blocks -- red top-left, green
top-right, blue bottom-left, white bottom-right, in panel coordinates --
straight into /dev/fb0, then records taps and reports which corner each
one FELL IN according to the reported coordinates. Tap the red block and
the verdict line says "red"; if it says "green" the X axis is mirrored,
"blue" means Y is mirrored, "white" means both.

The pattern is 1.4 MB of RGB565 but gzips to ~4 KB, so it goes over the
serial console in a few seconds like any other pushed file.

  tools/touch-axis-test.py --seconds 120
"""
import argparse, os, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, S = 568, 1232, 180
BLACK, RED, GREEN, BLUE, WHITE = 0x0000, 0xF800, 0x07E0, 0x001F, 0xFFFF

# Corner name -> the quadrant of the DIGITIZER's coordinate space it
# should land in if the axes are correct. Digitizer is 1024x2400.
TOUCH_W, TOUCH_H = 1024, 2400


def build_pattern(path):
    import struct
    rows = []
    for y in range(H):
        row = [BLACK] * W
        if y < S or y >= H - S:
            top = y < S
            for x in range(S):
                row[x] = RED if top else BLUE
            for x in range(W - S, W):
                row[x] = GREEN if top else WHITE
        rows.append(struct.pack('<%dH' % W, *row))
    with open(path, 'wb') as f:
        f.write(b''.join(rows))
    return W * H * 2


def console(cmds, wait=8, port=None):
    argv = [sys.executable, os.path.join(HERE, 'console.py')]
    if port:
        argv.append(port)
    argv.append('--wait=%s' % wait)
    argv += cmds
    return subprocess.run(argv, capture_output=True, text=True).stdout


def classify(x, y):
    """Which drawn corner does a reported (x, y) correspond to?"""
    left, top = x < TOUCH_W / 2, y < TOUCH_H / 2
    return {(True, True): 'red', (False, True): 'green',
            (True, False): 'blue', (False, False): 'white'}[(left, top)]


def parse(log):
    """Yield (down_time, x, y) once per contact, honouring ABS_MT_SLOT."""
    slot, ids, px, py = 0, {}, {}, {}
    pending = {}
    for line in log.splitlines():
        if 'ABS_MT_SLOT' in line:
            slot = int(line.rsplit(None, 1)[-1])
        elif 'ABS_MT_TRACKING_ID' in line:
            v = int(line.rsplit(None, 1)[-1])
            if v == -1:
                if slot in pending:
                    yield pending.pop(slot)
            else:
                ids[slot] = v
                pending[slot] = None
        elif 'ABS_MT_POSITION_X' in line:
            px[slot] = int(line.rsplit(None, 1)[-1])
        elif 'ABS_MT_POSITION_Y' in line:
            py[slot] = int(line.rsplit(None, 1)[-1])
        elif 'SYN_REPORT' in line:
            for s in list(pending):
                if pending[s] is None and s in px and s in py:
                    t = line.split()[2].rstrip(',')
                    pending[s] = (float(t), px[s], py[s])
    for v in pending.values():
        if v:
            yield v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=int, default=120)
    ap.add_argument('--port', default=None)
    a = ap.parse_args()

    tmp = tempfile.mkdtemp()
    fb = os.path.join(tmp, 'corners.fb')
    n = build_pattern(fb)
    print('pattern: %d bytes (%dx%d RGB565), %d px corner blocks' % (n, W, H, S))

    push = [sys.executable, os.path.join(HERE, 'push-file.py'),
            '--src', fb, '--dest', '/tmp/corners.fb']
    if a.port:
        push += ['--dev', a.port]
    subprocess.run(push, check=True)

    console(['cat /tmp/corners.fb > /dev/fb0; rm -f /tmp/axis.log; '
             'nohup evtest /dev/input/event0 > /tmp/axis.log 2>&1 & '
             'sleep 1; echo ARMED'], wait=6, port=a.port)
    print('\nTargets are on the panel. Tap RED, then WHITE. '
          '%d second window.\n' % a.seconds)
    time.sleep(a.seconds)

    console(['pkill evtest'], wait=4, port=a.port)
    log = console(['cat /tmp/axis.log'], wait=25, port=a.port)

    taps = list(parse(log))
    if not taps:
        print('no contacts recorded')
        return 1
    print('%d contacts:' % len(taps))
    for t, x, y in taps:
        print('  x=%-5d y=%-5d -> %s' % (x, y, classify(x, y)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
