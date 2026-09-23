#!/usr/bin/env python3
"""Board-side bounded midstream network-failure check for k230-video-session.

Run as root on the board after copying a host-generated fragmented MP4 to the
fixture path. The HTTP server advertises the complete Content-Length, streams a
prefix slowly, then closes before that length. This separates transport failure
from ordinary EOF. It records only allowlisted process/media facts.
"""
import argparse, http.server, json, os, pathlib, pwd, signal, socket, subprocess
import threading, time

RUNTIME = pathlib.Path('/run/shell')
STATE = RUNTIME / 'k230-video.pid'       # wrapper overrides Python default
LOG = RUNTIME / 'k230-video.log'


def proc(pid):
    p = pathlib.Path('/proc') / str(pid)
    a = p.joinpath('stat').read_text().rsplit(') ', 1)[1].split()
    return {'pid': pid, 'start': int(a[19]), 'pgrp': int(a[2]),
            'uid': p.stat().st_uid, 'state': a[0]}


def read_state(uid):
    try:
        d = json.loads(STATE.read_text())
        if d.get('uid') != uid or not d.get('controller'):
            return None
        c = proc(d['controller'])
        if c['uid'] != uid or c['start'] != d['controller_start'] or c['state'] == 'Z':
            return None
        if d.get('child'):
            ch = proc(d['child'])
            if ch['uid'] != uid or ch['start'] != d['child_start'] or ch['state'] == 'Z':
                return None
        return d
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return None


def ipc(controller, command):
    path = RUNTIME / ('k230-video-%d.sock' % controller)
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(1.5)
        s.connect(str(path))
        with s.makefile('rwb', buffering=0) as f:
            f.write((json.dumps({'command': command, 'request_id': 1}) + '\n').encode())
            deadline = time.monotonic() + 1.5
            while time.monotonic() < deadline:
                line = f.readline()
                if not line:
                    break
                reply = json.loads(line)
                if reply.get('request_id') == 1:
                    if reply.get('error') != 'success':
                        raise RuntimeError(reply.get('error', 'ipc error'))
                    return reply.get('data')
    raise RuntimeError('IPC response deadline')


def live_owned_groups(identities):
    found = []
    for entry in pathlib.Path('/proc').glob('[0-9]*'):
        try:
            p = proc(int(entry.name))
            for d in identities:
                if (p['pid'] == d['controller'] and p['start'] == d['controller_start']) or (
                        d.get('child') and p['pgrp'] == d['child']):
                    found.append(p)
                    break
        except (OSError, ValueError, IndexError):
            pass
    return found


class FaultServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'K230Fixture/1'
    protocol_version = 'HTTP/1.1'

    def do_GET(self):
        srv = self.server
        if self.path != '/fixture.mp4' or srv.faulted.is_set():
            self.send_error(503)
            return
        payload = srv.payload
        self.send_response(200)
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Connection', 'close')
        self.end_headers()
        sent = 0
        try:
            while sent < len(payload):
                n = min(srv.chunk, len(payload) - sent)
                self.wfile.write(payload[sent:sent + n])
                self.wfile.flush()
                sent += n
                srv.bytes_sent = sent
                if sent >= srv.minimum_bytes and time.monotonic() >= srv.fault_due:
                    srv.faulted.set()
                    srv.truncated = sent < len(payload)
                    self.close_connection = True
                    return
                time.sleep(srv.delay)
        except (BrokenPipeError, ConnectionResetError, OSError):
            srv.faulted.set()
            srv.truncated = sent < len(payload)

    def log_message(self, *_args):
        return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('fixture', type=pathlib.Path)
    ap.add_argument('--session', default='/run/current-system/sw/bin/k230-video-session')
    ap.add_argument('--max-seconds', type=float, default=45)
    ap.add_argument('--fault-after', type=float, default=8)
    ap.add_argument('--delay', type=float, default=.08)
    args = ap.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('run as root so the session can be launched as shell')
    fixture = args.fixture.read_bytes()
    if len(fixture) < 65536:
        raise SystemExit('fixture is too small for a midstream test')
    user = pwd.getpwnam('shell')
    identities = []
    playlist = RUNTIME / 'k230-midstream-failure.playlist'
    server = FaultServer(('127.0.0.1', 0), Handler)
    server.payload = fixture
    server.chunk, server.delay = 32768, args.delay
    server.minimum_bytes = min(len(fixture) - 1, 512 * 1024)
    server.fault_due = float('inf')
    server.faulted = threading.Event(); server.truncated = False; server.bytes_sent = 0
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    child = None
    log_before = LOG.read_bytes() if LOG.is_file() else b''
    report = {'fixture_bytes': len(fixture), 'fault_endpoint': 'loopback',
              'fault_after_observed_media_seconds': 2, 'fault_delay_after_armed_seconds': 1, 'events': []}
    try:
        playlist.write_text('http://127.0.0.1:%d/fixture.mp4\n' % server.server_port)
        os.chown(playlist, user.pw_uid, user.pw_gid); playlist.chmod(0o600)
        env = os.environ.copy()
        env.update({'XDG_RUNTIME_DIR': str(RUNTIME), 'WAYLAND_DISPLAY': 'wayland-1',
                    'SWAYSOCK': str(RUNTIME / 'sway-ipc.sock')})
        child = subprocess.Popen(['runuser', '-u', 'shell', '--', 'env', *[
            '%s=%s' % (k, v) for k, v in env.items() if k in ('XDG_RUNTIME_DIR', 'WAYLAND_DISPLAY', 'SWAYSOCK')],
            args.session, 'run', '--url-file', str(playlist)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + args.max_seconds
        started = False
        while time.monotonic() < deadline and child.poll() is None:
            d = read_state(user.pw_uid)
            if d and d not in identities:
                identities.append(d.copy())
            if d and d.get('child'):
                try:
                    pos = ipc(d['controller'], ['get_property', 'time-pos'])
                    eof = ipc(d['controller'], ['get_property', 'eof-reached'])
                    report['events'].append({'time_pos': pos, 'eof_reached': eof})
                    if isinstance(pos, (int, float)) and pos >= 2:
                        if not started:
                            server.fault_due = time.monotonic() + 1
                        started = True
                except (OSError, ValueError, RuntimeError, KeyError):
                    pass
            if server.faulted.is_set():
                break
            time.sleep(.2)
        if not started:
            raise RuntimeError('fault did not follow observed media time-pos >= 2')
        if not server.faulted.wait(max(0, deadline - time.monotonic())):
            raise RuntimeError('fixture server did not perform truncated response')
        report['fault_bytes_sent'] = server.bytes_sent
        report['declared_bytes'] = len(fixture)
        report['truncated_response'] = server.truncated and server.bytes_sent < len(fixture)
        if not report['truncated_response']:
            raise RuntimeError('response was not truncated before declared Content-Length')
        remaining = max(0, deadline - time.monotonic())
        child.wait(timeout=remaining)
        report['controller_exit'] = child.returncode
        if child.returncode == 0:
            raise RuntimeError('controller treated truncated response as successful EOF')
        report['natural_eof_marker'] = False
        if LOG.is_file():
            current = LOG.read_bytes() if LOG.is_file() else b''
            appended = current[len(log_before):] if current.startswith(log_before) else current
            text = appended.decode(errors='replace')
            report['natural_eof_marker'] = 'End of file' in text
        if report['natural_eof_marker']:
            raise RuntimeError('log reported ordinary End of file')
        report['cleanup_before_stop'] = {
            'state_absent': not STATE.exists(),
            'socket_absent': not list(RUNTIME.glob('k230-video-*.sock')),
            'owned_groups_absent': not live_owned_groups(identities),
            'playlist_removed': not playlist.exists(),
        }
        if not all(report['cleanup_before_stop'].values()):
            raise RuntimeError('controller exited without complete cleanup')
        report['result'] = 'pass'
        print(json.dumps(report, sort_keys=True))
        return 0
    except Exception as error:
        report['result'] = 'fail'
        report['error'] = str(error)
        report['cleanup_observed'] = {
            'state_absent': not STATE.exists(),
            'socket_absent': not list(RUNTIME.glob('k230-video-*.sock')),
            'owned_groups_absent': not live_owned_groups(identities),
            'playlist_removed': not playlist.exists(),
        }
        print(json.dumps(report, sort_keys=True))
        return 1
    finally:
        if child is not None and child.poll() is None:
            subprocess.run(['runuser', '-u', 'shell', '--', args.session, 'stop'], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=8, check=False)
            try: child.wait(timeout=8)
            except subprocess.TimeoutExpired: pass
        try: playlist.unlink()
        except FileNotFoundError: pass
        server.shutdown(); server.server_close(); thread.join(timeout=2)


if __name__ == '__main__':
    raise SystemExit(main())
