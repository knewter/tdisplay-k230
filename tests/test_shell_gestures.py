"""Host checks for finger-tracked drawer scrolling and tap/hold ownership."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = ("drawer-drag", "flick-stop", "finger-coast", "cancel-below-threshold", "tap-launch",
         "hold-cue", "move-cancel", "back-cancel", "second-contact")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", choices=CASES)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temp:
        executable = Path(temp) / "shell-drawer-test"
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-I",
                        str(ROOT / "nix/touch-launcher"),
                        str(ROOT / "tests/shell_drawer_driver.c"), "-o", str(executable)], check=True)
        for case in args.case or CASES:
            subprocess.run([str(executable), case], check=True, capture_output=True)
            print(f"PASS {case}")


if __name__ == "__main__":
    main()
