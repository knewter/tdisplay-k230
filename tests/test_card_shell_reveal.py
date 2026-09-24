#!/usr/bin/env python3
"""Native bounded IPC proof for the opt-in compositor-to-Rust reveal stream."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

SOURCE = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include "sway/card_shell_route.h"

static void finish(struct card_shell_reveal_stream *stream) {
    for (int i=0; i<100 && stream->active; i++) {
        assert(card_shell_reveal_pump(stream));
        usleep(1000);
    }
    assert(!stream->active);
}
int main(int argc, char **argv) {
    assert(argc==2);
    struct card_shell_drawer_gesture gesture={0};
    card_shell_drawer_down(&gesture,7,200,1100);
    assert(card_shell_reveal_progress(&gesture,205,1030,700,false)==100);
    assert(card_shell_reveal_progress(&gesture,300,1050,700,false)==71);
    /* Horizontal displacement cannot reset a vertically dragged panel. */
    assert(card_shell_reveal_progress(&gesture,400,1030,700,false)==100);
    assert(card_shell_reveal_progress(&gesture,200,1200,700,false)==0);
    card_shell_drawer_down(&gesture,8,200,1100);
    assert(card_shell_reveal_progress(&gesture,200,1000,700,false)==0);
    assert(card_shell_reveal_enabled());
    struct card_shell_reveal_stream stream={0};
    if (!strcmp(argv[1],"missing") || !strcmp(argv[1],"unsafe")) {
        assert(!card_shell_reveal_begin(&stream,"drawer"));
        return 0;
    }
    assert(card_shell_reveal_begin(&stream,"drawer"));
    assert(card_shell_reveal_update(&stream,125));
    assert(card_shell_reveal_update(&stream,350));
    if (!strcmp(argv[1],"pause")) {
        usleep(600000);
        assert(card_shell_reveal_pump(&stream));
        assert(stream.active);
        assert(card_shell_reveal_update(&stream,400));
    }
    assert(card_shell_reveal_finish(&stream,true));
    finish(&stream);
    if (!strcmp(argv[1],"pair")) {
        assert(card_shell_reveal_begin(&stream,"shade"));
        assert(card_shell_reveal_update(&stream,500));
        card_shell_reveal_cancel(&stream);
        finish(&stream);
    }
    return 0;
}
'''


class RevealStream(unittest.TestCase):
    def test_protocol_failure_and_idle_hold(self):
        with tempfile.TemporaryDirectory(prefix="card-reveal-") as directory:
            runtime = Path(directory)
            runtime.chmod(0o700)
            include = runtime / "sway"
            include.mkdir()
            (include / "card_shell_route.h").write_bytes(
                (ROOT / "nix/card-shell/route.h").read_bytes())
            source = runtime / "test.c"
            source.write_text(SOURCE)
            binary = runtime / "test"
            subprocess.run([os.environ.get("CC", "cc"), "-std=gnu11", "-Wall", "-Wextra",
                            "-Werror", "-I" + str(runtime), str(source),
                            str(ROOT / "nix/card-shell/route.c"), "-lm", "-o", str(binary)],
                           check=True)
            path = runtime / "k230-shell-rust.sock"
            env = os.environ | {"XDG_RUNTIME_DIR": str(runtime),
                                "SWAY_K230_CARD_SURFACE_SOCKET": str(path),
                                "SWAY_K230_CARD_REVEAL_STREAM": "1"}
            subprocess.run([binary, "missing"], env=env, check=True)
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.addCleanup(listener.close)
            listener.bind(str(path))
            listener.listen(3)
            path.chmod(0o666)
            subprocess.run([binary, "unsafe"], env=env, check=True)
            path.chmod(0o600)
            subprocess.run([binary, "pair"], env=env, check=True)
            messages = []
            for _ in range(2):
                client, _ = listener.accept()
                with client:
                    data = b""
                    while chunk := client.recv(4096):
                        data += chunk
                frames = data.splitlines(keepends=True)
                self.assertTrue(all(len(frame) <= 128 and frame.endswith(b"\n")
                                    for frame in frames))
                messages.append([json.loads(frame) for frame in frames])
            self.assertEqual([frame["phase"] for frame in messages[0]][0], "begin")
            self.assertEqual([frame["phase"] for frame in messages[0]][-1], "finish")
            self.assertEqual(messages[0][-1]["progress"], 1000)
            self.assertEqual([frame["phase"] for frame in messages[1]][-1], "cancel")
            self.assertEqual(messages[1][-1]["progress"], 0)
            self.assertNotEqual(messages[0][0]["seq"], messages[1][0]["seq"])
            self.assertEqual({frame["seq"] for frame in messages[0]},
                             {messages[0][0]["seq"]})
            self.assertEqual({frame["seq"] for frame in messages[1]},
                             {messages[1][0]["seq"]})
            for frames in messages:
                for frame in frames:
                    self.assertEqual(frame["v"], 1)
                    self.assertEqual(frame["kind"], "reveal")
                    self.assertIn(frame["surface"], ("drawer", "shade"))
                    self.assertGreaterEqual(frame["progress"], 0)
                    self.assertLessEqual(frame["progress"], 1000)
            subprocess.run([binary, "pause"], env=env, check=True)
            client, _ = listener.accept()
            with client:
                data = b""
                while chunk := client.recv(4096):
                    data += chunk
            paused = [json.loads(line) for line in data.splitlines()]
            self.assertEqual(paused[-1]["phase"], "finish")
            self.assertIn(400, [frame["progress"] for frame in paused])


if __name__ == "__main__":
    unittest.main()
