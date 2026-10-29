# Task 3.2 board proof: video wallpaper decoding stops while the display is off.
# Runs as root on the board; theme and sway calls drop to the shell user.
import json, os, pwd, subprocess, sys, time
from pathlib import Path
THEME = '43a0582fc5957b38b0e2aff6'          # everforest (builtin)
VIDEO = '17718025235b87ba734b0562'          # user-motion-test.mp4 overlay
STILL = '91f276073b5b871841aef6dc'          # 1-tree-tops.webp (restored afterwards)
STATUS = Path('/run/shell/k230-wallpaper-status.json')
u = pwd.getpwnam('shell')
def drop(): os.setgroups([]); os.setgid(u.pw_gid); os.setuid(u.pw_uid)
pid = subprocess.check_output(['pgrep', '-x', 'k230-shell-rust'], text=True).split()[0]
env = {k.decode(): v.decode() for k, v in (x.split(b'=', 1) for x in Path('/proc', pid, 'environ').read_bytes().split(b'\0') if b'=' in x)}
sway_pid = subprocess.check_output(['systemctl', 'show', '-p', 'MainPID', '--value', 'shell'], text=True).strip()
swaymsg = str(Path(os.path.realpath(f'/proc/{sway_pid}/exe')).parent / 'swaymsg')
def theme(*a):
    p = subprocess.run([env['K230_THEME_COMMAND'], *a, '--json'], env=env, preexec_fn=drop, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-400:]
    return json.loads(p.stdout)
def sway(cmd):
    return subprocess.run([swaymsg, '-s', '/run/shell/sway-ipc.sock', cmd], env=env, preexec_fn=drop, capture_output=True, text=True, timeout=20).stdout.strip()
def st():
    v = json.loads(STATUS.read_text()); v['t'] = round(time.monotonic(), 3); return v
def cpu(p):
    try:
        f = Path(f'/proc/{p}/stat').read_text().rsplit(')', 1)[1].split(); return int(f[11]) + int(f[12])
    except (OSError, TypeError): return None
def dpms():
    return {c.name: (c / 'dpms').read_text().strip() for c in Path('/sys/class/drm').iterdir() if (c / 'dpms').exists() and (c / 'status').read_text().strip() == 'connected'}
def wait(pred, secs):
    end = time.monotonic() + secs
    while time.monotonic() < end:
        v = st()
        if pred(v): return v
        time.sleep(0.25)
    raise RuntimeError('timeout: ' + json.dumps(st()))
KEYS = ('state', 'decoder_pid', 'frames_decoded', 'frames_submitted', 'frame_callbacks', 't')
short = lambda v: {k: v[k] for k in KEYS}
r = {'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
try:
    pv = theme('preview', THEME, '--background', VIDEO)
    a = theme('activate', THEME, '--background', VIDEO, '--expected-generation', pv['generation']); assert a.get('activated') is True
    sway('card_shell home')
    v0 = wait(lambda v: v['state'] == 'playing' and v['frames_decoded'] > 30, 40)
    time.sleep(3); v1 = st()
    dp = v1['decoder_pid']; c1 = cpu(dp); time.sleep(3); v2 = st(); c2 = cpu(dp)
    r['on_before'] = {'dpms': dpms(), 'a': short(v1), 'b': short(v2), 'decoder_cpu_ticks_3s': None if c1 is None or c2 is None else c2 - c1}
    t_off = time.monotonic(); r['power_off_reply'] = sway('output * power off')
    trace = []
    while time.monotonic() - t_off < 10:
        trace.append(short(st())); time.sleep(0.1)
    stop = next((x for x in trace if x['state'] != 'playing'), None)
    r['off_state_change_ms'] = None if stop is None else round((stop['t'] - t_off) * 1000)
    last = trace[-1]; mid = next(x for x in trace if x['t'] - t_off >= 5)
    r['off'] = {'dpms': dpms(), 'first': trace[0], 'first_not_playing': stop, 'at_5s': mid, 'at_10s': last,
                'frames_decoded_5s_to_10s': last['frames_decoded'] - mid['frames_decoded'],
                'old_decoder_alive': Path(f'/proc/{dp}').exists(), 'old_decoder_cpu_ticks_now': cpu(dp)}
    c3 = cpu(dp); time.sleep(3); c4 = cpu(dp)
    r['off']['old_decoder_cpu_ticks_3s'] = None if c3 is None or c4 is None else c4 - c3
    t_on = time.monotonic(); r['power_on_reply'] = sway('output * power on')
    v3 = wait(lambda v: v['state'] == 'playing', 15); time.sleep(3); v4 = st()
    r['on_after'] = {'dpms': dpms(), 'playing_ms': round((v3['t'] - t_on) * 1000), 'a': short(v3), 'b': short(v4)}
finally:
    sway('output * power on')
    pv = theme('preview', THEME, '--background', STILL)
    a = theme('activate', THEME, '--background', STILL, '--expected-generation', pv['generation'])
    r['restored_still'] = a.get('activated') is True
    r['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    print(json.dumps(r, indent=2))
