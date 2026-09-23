#!/usr/bin/env python3
from card_shell_test_support import exercise
exercise('recovery', ['cancel-no-up-return', 'output-loss-restores', 'topbar-restores-normal',
                      'global-edge-entry', 'persistent-button', 'expand-focus-keyboard'])
exercise('disabled', [], disabled=True)
