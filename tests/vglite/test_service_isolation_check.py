#!/usr/bin/env python3
"""Host fixtures for a physical-only normal-service isolation checker."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[2]/'tools/vglite-service-isolation-check.py'
spec=importlib.util.spec_from_file_location('isolation',SOURCE)
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class IsolationChecks(unittest.TestCase):
    def test_broker_grants_exact_old_and_new_pid_and_denial(self):
        trial={'created_at_utc':'2026-09-23T00:00:00Z'}
        def journal(lines):
            return patch.object(M.subprocess,'run',return_value=types.SimpleNamespace(stdout='\n'.join(lines)))
        grant=lambda pid:'VG-Lite descriptor granted to compositor MainPID '+str(pid)
        deny='VG-Lite descriptor denied: Denied peer is not compositor MainPID'
        with journal([grant(101),deny]):
            self.assertEqual(M.broker_counts(trial,None,101)['current_pid_grants'],1)
        with journal([grant(101),deny,grant(202),deny]):
            result=M.broker_counts(trial,101,202)
            self.assertEqual((result['old_pid_grants'],result['current_pid_grants']),(1,1))
        for lines in ([grant(101),grant(101),grant(202),deny],
                      [grant(101),grant(202)], [grant(101),grant(303),deny]):
            with self.subTest(lines=lines),journal(lines):
                with self.assertRaises(RuntimeError):M.broker_counts(trial,101,202)

    def test_same_uid_result_requires_every_denial(self):
        ok={'caps_zero':True,'broker_denied':True,'direct_denied':True,
            'proc_fd_denied':True,'ptrace_denied':True,'shell_uid':1000}
        def run(value):return types.SimpleNamespace(returncode=0,stdout=json.dumps(value))
        with patch.object(M.pwd,'getpwnam',return_value=types.SimpleNamespace(pw_uid=1000,pw_gid=1000)), \
             patch.object(M.subprocess,'run',return_value=run(ok)):
            self.assertEqual(M.run_denial(100,7)['ptrace_denied'],True)
        for key in ('caps_zero','broker_denied','direct_denied','proc_fd_denied','ptrace_denied'):
            bad=dict(ok);bad[key]=False
            with self.subTest(key=key),patch.object(M.pwd,'getpwnam',return_value=types.SimpleNamespace(pw_uid=1000,pw_gid=1000)), \
                 patch.object(M.subprocess,'run',return_value=run(bad)):
                with self.assertRaisesRegex(RuntimeError,'isolation denial failed'):M.run_denial(100,7)

    def test_sway_launched_postexec_child_checked_over_authenticated_socket(self):
        with tempfile.TemporaryDirectory() as directory:
            sockets=Path(directory)
            child=[]
            def launch(command):
                nonce=command.split('--nonce ')[1].strip().split()[0]
                path=next(sockets.glob('k230-vglite-isolation-*.sock'))
                def connect():
                    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as peer:
                        peer.connect(str(path));peer.sendall(nonce.encode());peer.recv(2)
                thread=threading.Thread(target=connect);thread.start();child.append(thread)
            with patch.object(M,'SOCKET_DIR',sockets), \
                 patch.object(M,'sway_command',side_effect=launch), \
                 patch.object(M,'ancestor_is_sway',return_value=True), \
                 patch.object(M,'uid_and_caps',return_value=([os.getuid()]*4,0)), \
                 patch.object(M,'device_fd_numbers',return_value=[]), \
                 patch.object(M,'mapped_device',return_value=0), \
                 patch.object(M.pwd,'getpwnam',return_value=types.SimpleNamespace(pw_uid=os.getuid())):
                report=M.run_app_check(123)
                self.assertEqual(report['app_device_fds'],0)
                self.assertEqual(report['app_device_mappings'],0)
                self.assertEqual(report['preexec_inspection'],'UNVERIFIED')
            for thread in child:thread.join(timeout=2)
            self.assertEqual(list(sockets.iterdir()),[])

    def test_sway_ipc_command_requires_successful_bounded_response(self):
        with tempfile.TemporaryDirectory() as directory:
            address=Path(directory)/'sway.sock'
            received=[]
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
                server.bind(str(address));server.listen(1)
                def respond():
                    peer,_=server.accept()
                    with peer:
                        header=b''
                        while len(header)<14:header+=peer.recv(14-len(header))
                        size,kind=__import__('struct').unpack('<II',header[6:])
                        payload=b''
                        while len(payload)<size:payload+=peer.recv(size-len(payload))
                        received.append((header[:6],kind,payload))
                        body=b'[{"success":true}]'
                        answer=b'i3-ipc'+__import__('struct').pack('<II',len(body),0)+body
                        peer.sendall(answer[:3]);peer.sendall(answer[3:])
                thread=threading.Thread(target=respond);thread.start()
                with patch.object(M,'SWAYSOCK',address):M.sway_command('exec -- /bin/true')
                thread.join(timeout=2)
            self.assertEqual(received,[(b'i3-ipc',0,b'exec -- /bin/true')])

    def test_trial_token_phase_and_watchdog_restoration_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            state={'token':'a'*32,'phase':'observed','main_pid':101,'normal_system':'/nix/store/system',
                   'boot_id':'boot','unwrapped':'/nix/store/sway','created_at_utc':'2026-09-23T00:00:00Z'}
            (root/'state.json').write_text(json.dumps(state))
            report=root/'isolation-initial.json'
            with self.assertRaisesRegex(RuntimeError,'token, phase'):
                M.check_trial(root,'b'*32,'initial',101,None,report)
            state['phase']='restored';(root/'state.json').write_text(json.dumps(state))
            with self.assertRaisesRegex(RuntimeError,'token, phase'):
                M.check_trial(root,'a'*32,'initial',101,None,report)
            self.assertFalse(report.exists())


if __name__=='__main__':unittest.main()
