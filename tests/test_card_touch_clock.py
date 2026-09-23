#!/usr/bin/env python3
"""Execute the actual adapter clock conversion across source timestamp wrap."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TouchClock(unittest.TestCase):
    def test_delayed_future_wrap_and_startup(self):
        source = (ROOT/'nix/card-shell/adapter.c').read_text()
        function = source[source.index('static uint64_t event_time_ms('):source.index('static bool enabled(')]
        program = '''#include <stdint.h>
#include <assert.h>
static uint64_t clock_ms;
static uint64_t now_ms(void) { return clock_ms; }
''' + function + '''
int main(void) {
    clock_ms=10000; assert(event_time_ms(9800)==9800);
    assert(event_time_ms(10005)==10005);
    clock_ms=UINT64_C(4294967296)+20;
    assert(event_time_ms(UINT32_MAX-9)==UINT64_C(4294967296)-10);
    assert(event_time_ms(10)==UINT64_C(4294967296)+10);
    clock_ms=UINT64_C(4294967296)-10;
    assert(event_time_ms(10)==UINT64_C(4294967296)+10);
    clock_ms=UINT64_C(4294967296)*4+1000;
    assert(event_time_ms(800)==UINT64_C(4294967296)*4+800);
    clock_ms=0; assert(event_time_ms(UINT32_MAX)==0);
}
'''
        with tempfile.TemporaryDirectory(prefix='card-touch-clock-') as directory:
            root=Path(directory); (root/'test.c').write_text(program)
            subprocess.run([os.environ.get('CC','cc'), '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', str(root/'test.c'), '-o', str(root/'test')], check=True)
            subprocess.run([str(root/'test')], check=True)


if __name__ == '__main__': unittest.main()
