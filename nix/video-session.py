#!/usr/bin/env python3
import argparse, fcntl, json, os, signal, socket, stat, subprocess, sys, time
from pathlib import Path

PUBLIC = os.environ.get('K230_VIDEO_PUBLIC_URL', 'https://dash.akamaized.net/akamai/bbb_30fps/bbb_30fps.mpd')
RUNTIME = Path(os.environ.get('K230_VIDEO_RUNTIME_DIR', '/run/shell'))
STATE = Path(os.environ.get('K230_VIDEO_PID_FILE', RUNTIME / 'k230-video.json'))
LOCK = Path(os.environ.get('K230_VIDEO_LOCK_FILE', RUNTIME / 'k230-video.lock'))
LOG = Path(os.environ.get('K230_VIDEO_LOG', RUNTIME / 'k230-video.log'))
PLAYER = os.environ.get('K230_VIDEO_PLAYER', 'mpv')
DEADLINE = float(os.environ.get('K230_VIDEO_DEADLINE', '30'))
UID = os.getuid()


def starttime(pid):
    try:
        text = Path(f'/proc/{pid}/stat').read_text()
        return int(text.rsplit(') ', 1)[1].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def owned_state(data):
    if not isinstance(data, dict): return False
    fields = ('uid', 'controller', 'controller_start', 'child', 'child_start')
    if any(not isinstance(data.get(k), int) or data[k] <= 0 for k in fields): return False
    return (data['uid'] == UID and data['controller_start'] == starttime(data['controller'])
            and data['child_start'] == starttime(data['child']))


def read_state():
    try:
        data = json.loads(STATE.read_text())
        return data if owned_state(data) else None
    except (OSError, ValueError, TypeError):
        return None


def write_state(child):
    data = {'uid': UID, 'controller': os.getpid(), 'controller_start': starttime(os.getpid()),
            'child': child.pid, 'child_start': starttime(child.pid)}
    temp = STATE.with_name(STATE.name + f'.{os.getpid()}.tmp')
    temp.write_text(json.dumps(data) + '\n')
    os.chmod(temp, 0o600)
    os.replace(temp, STATE)


def kill_group(proc, sig):
    try:
        os.killpg(proc.pid, sig)
    except ProcessLookupError:
        pass


def validate_playlist(explicit):
    path = Path(explicit) if explicit else RUNTIME / 'k230-video.playlist'
    if path.is_symlink():
        raise RuntimeError('video URL file must not be a symlink')
    if explicit and not path.exists():
        raise RuntimeError('video URL file is absent')
    if not path.exists():
        return PUBLIC, None
    if not path.is_file():
        raise RuntimeError('video URL file must be a regular non-symlink file')
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode != 0o600 or path.stat().st_uid != UID:
        raise RuntimeError('video URL file must be owner-only and owned by the session user')
    return str(path), path


class Session:
    def __init__(self, mode, explicit):
        self.mode, self.explicit = mode, explicit
        self.cancelled = False
        self.child = None
        self.socket = RUNTIME / f'k230-video-{os.getpid()}.sock'
        self.private_path = None
        self.lock = None
        self.cancel_deadline = None

    def signal(self, _signum, _frame):
        self.cancelled = True
        self.cancel_deadline = time.monotonic() + 2
        if self.child is not None:
            kill_group(self.child, signal.SIGTERM)

    def args(self, mode, source):
        public = not source.startswith('/')
        if mode == 'mvx':
            decoder, geometry, app, extras = '--vd=h264_v4l2m2m', '568x320', 'k230-video-mvx', ['--correct-pts=no', '--container-fps-override=30', '--sws-scaler=point']
        else:
            decoder, geometry, app, extras = '--vd=h264', '480x270', 'k230-video-software', []
        args = [PLAYER, '--no-config', '--vo=wlshm', '--profile=sw-fast', '--hwdec=no', decoder,
                '--audio=no', '--cache=yes', '--demuxer-readahead-secs=30', '--network-timeout=10',
                '--title=k230-video', '--force-window=yes', f'--geometry={geometry}',
                f'--wayland-app-id={app}', f'--input-ipc-server={self.socket}'] + extras
        if public:
            args += ['--vid=7' if mode == 'mvx' else '--vid=6', source]
        else:
            args += ['--vid=auto', f'--playlist={source}']
        return args

    def run_once(self, mode, source):
        try: self.socket.unlink()
        except FileNotFoundError: pass
        output = subprocess.DEVNULL if source.startswith('/') else open(LOG, 'ab', buffering=0)
        try:
            self.child = subprocess.Popen(self.args(mode, source), stdout=output, stderr=subprocess.STDOUT,
                                          start_new_session=True, close_fds=True)
            write_state(self.child)
            deadline = time.monotonic() + DEADLINE
            timed_out = False
            while True:
                rc = self.child.poll()
                if rc is not None:
                    return rc, timed_out
                if self.cancelled:
                    kill_group(self.child, signal.SIGTERM)
                    if time.monotonic() >= self.cancel_deadline:
                        kill_group(self.child, signal.SIGKILL)
                elif not self.socket.exists() and time.monotonic() >= deadline:
                    timed_out = True
                    kill_group(self.child, signal.SIGTERM)
                if timed_out:
                    try: self.child.wait(timeout=2)
                    except subprocess.TimeoutExpired: kill_group(self.child, signal.SIGKILL)
                time.sleep(.05)
        finally:
            if self.child is not None:
                kill_group(self.child, signal.SIGTERM)
                try: self.child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    kill_group(self.child, signal.SIGKILL); self.child.wait()
            if self.child is not None:
                self.child.wait()
            if hasattr(output, 'close'): output.close()
            try: self.socket.unlink()
            except FileNotFoundError: pass
            try:
                if STATE.exists():
                    state = json.loads(STATE.read_text())
                    if isinstance(state, dict) and state.get('controller') == os.getpid(): STATE.unlink()
            except (OSError, ValueError, TypeError): pass
            self.child = None

    def run(self):
        RUNTIME.mkdir(parents=True, exist_ok=True); os.umask(0o077)
        LOG.touch(exist_ok=True); os.chmod(LOG, 0o600)
        self.lock = open(LOCK, 'a+')
        os.chmod(LOCK, 0o600)
        try: fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: print('video is already starting or running', file=sys.stderr); return 1
        source, self.private_path = validate_playlist(self.explicit)
        old = [signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)]
        for s in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT): signal.signal(s, self.signal)
        try:
            if self.mode == 'mvx' and self.private_path is not None:
                raise RuntimeError('MVX mode is limited to the public demo')
            if self.cancelled: return 143
            rc, timed = self.run_once(self.mode, source)
            if self.mode == 'mvx' and rc != 0 and not timed and not self.cancelled:
                print('MVX decoder failed; falling back to software H.264', file=sys.stderr)
                rc, _ = self.run_once('software', source)
            return rc
        finally:
            if self.private_path is not None:
                try: self.private_path.unlink()
                except FileNotFoundError: pass
            for s, old_handler in zip((signal.SIGTERM, signal.SIGHUP, signal.SIGINT), old): signal.signal(s, old_handler)
            self.lock.close()


def stop():
    data = read_state()
    if not data:
        try:
            if STATE.is_file() and not STATE.is_symlink() and STATE.stat().st_uid == UID: STATE.unlink()
        except OSError: pass
        return 0
    try: os.kill(data['controller'], signal.SIGTERM)
    except ProcessLookupError: pass
    return 0


def main():
    p = argparse.ArgumentParser(); p.add_argument('command', choices=('run', 'run-mvx', 'stop', 'status')); p.add_argument('--url-file', default=os.environ.get('K230_VIDEO_URL_FILE', ''))
    a = p.parse_args()
    if a.command == 'stop': return stop()
    if a.command == 'status': return 0 if read_state() else 1
    return Session('mvx' if a.command == 'run-mvx' else os.environ.get('K230_VIDEO_MODE', 'software'), a.url_file).run()

if __name__ == '__main__': sys.exit(main())
