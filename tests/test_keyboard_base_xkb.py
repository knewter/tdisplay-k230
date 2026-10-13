"""The k230-base keymap gives LILYGO's printed symbols (keyboard-base task 3.2).

Drives libxkbcommon itself: the keymap file is compiled, modifier keys are
pressed on an xkb_state, and the keysym each key then produces is compared
with LILYGO's Shift table. Needs libxkbcommon; set XKBCOMMON_LIB to its
shared object if ctypes cannot find it, e.g.

  XKBCOMMON_LIB=$(nix build --no-link --print-out-paths nixpkgs#libxkbcommon)/lib/libxkbcommon.so \
    python3 -m unittest tests/test_keyboard_base_xkb.py
"""
import ctypes
import ctypes.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
KEYMAP = ROOT / "nix/keyboard-base/k230-base.xkb"

# LILYGO extension_keyboard_shift_symbol_for_code(), by printed letter.
SHIFT_SYMBOLS = {
    "Q": "`", "W": "~", "E": "-", "R": "+", "T": "=", "Y": "\\", "U": "|",
    "I": ";", "O": ":", "P": '"', "A": "~", "S": "[", "D": "]", "F": "{",
    "G": "}", "H": ",", "J": "`", "K": "/", "L": "?", "B": ".", "N": "<",
    "M": ">",
}
DIGIT_SHIFT = dict(zip("1234567890", "!@#$%^&*()"))
KEYNAME = {c: n for c, n in zip("QWERTYUIOP", [f"AD{i:02d}" for i in range(1, 11)])}
KEYNAME.update({c: n for c, n in zip("ASDFGHJKL", [f"AC{i:02d}" for i in range(1, 10)])})
KEYNAME.update({c: n for c, n in zip("ZXCVBNM", [f"AB{i:02d}" for i in range(1, 8)])})
KEYNAME.update({d: f"AE{i:02d}" for i, d in enumerate("1234567890", 1)})


def load():
    path = os.environ.get("XKBCOMMON_LIB") or ctypes.util.find_library("xkbcommon")
    if not path:
        raise unittest.SkipTest("libxkbcommon not found; set XKBCOMMON_LIB")
    lib = ctypes.CDLL(path)
    lib.xkb_context_new.restype = ctypes.c_void_p
    lib.xkb_keymap_new_from_string.restype = ctypes.c_void_p
    lib.xkb_keymap_new_from_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
    lib.xkb_keymap_key_by_name.restype = ctypes.c_uint32
    lib.xkb_keymap_key_by_name.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.xkb_state_new.restype = ctypes.c_void_p
    lib.xkb_state_new.argtypes = [ctypes.c_void_p]
    lib.xkb_state_update_key.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int]
    lib.xkb_state_key_get_one_sym.restype = ctypes.c_uint32
    lib.xkb_state_key_get_one_sym.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    lib.xkb_keysym_to_utf32.restype = ctypes.c_uint32
    lib.xkb_keysym_to_utf32.argtypes = [ctypes.c_uint32]
    lib.xkb_keysym_get_name.argtypes = [ctypes.c_uint32, ctypes.c_char_p, ctypes.c_size_t]
    return lib


class K230BaseKeymap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = load()
        ctx = cls.lib.xkb_context_new(0)
        cls.keymap = cls.lib.xkb_keymap_new_from_string(ctx, KEYMAP.read_bytes(), 1, 0)
        if not cls.keymap:
            raise AssertionError("k230-base.xkb did not compile")

    def key(self, name):
        code = self.lib.xkb_keymap_key_by_name(self.keymap, name.encode())
        self.assertNotEqual(code, 0, name)
        return code

    def type_with(self, held, name, caps=False):
        state = self.lib.xkb_state_new(self.keymap)
        if caps:
            self.lib.xkb_state_update_key(state, self.key("CAPS"), 1)
            self.lib.xkb_state_update_key(state, self.key("CAPS"), 0)
        for h in held:
            self.lib.xkb_state_update_key(state, self.key(h), 1)
        return self.lib.xkb_state_key_get_one_sym(state, self.key(name))

    def char(self, sym):
        return chr(self.lib.xkb_keysym_to_utf32(sym))

    def symname(self, sym):
        buf = ctypes.create_string_buffer(64)
        self.lib.xkb_keysym_get_name(sym, buf, 64)
        return buf.value.decode()

    def test_letters(self):
        for letter, name in KEYNAME.items():
            if not letter.isalpha():
                continue
            self.assertEqual(self.char(self.type_with([], name)), letter.lower(), letter)
            self.assertEqual(self.char(self.type_with([], name, caps=True)), letter, letter)

    def test_shift_gives_printed_symbol(self):
        for letter, symbol in SHIFT_SYMBOLS.items():
            name = KEYNAME[letter]
            self.assertEqual(self.char(self.type_with(["LFSH"], name)), symbol, letter)
            self.assertEqual(self.char(self.type_with(["LFSH"], name, caps=True)), symbol, letter)

    def test_unprinted_letters_shift_to_capitals(self):
        for letter in "ZXCV":
            self.assertEqual(self.char(self.type_with(["LFSH"], KEYNAME[letter])), letter)

    def test_digit_row(self):
        for digit, symbol in DIGIT_SHIFT.items():
            self.assertEqual(self.char(self.type_with([], KEYNAME[digit])), digit)
            self.assertEqual(self.char(self.type_with(["LFSH"], KEYNAME[digit])), symbol)

    def test_fn_layer(self):
        for key, plain, fn in [("UP", "Up", "Prior"), ("DOWN", "Down", "Next"),
                               ("LEFT", "Left", "Home"), ("RGHT", "Right", "End"),
                               ("BKSP", "BackSpace", "Insert")]:
            self.assertEqual(self.symname(self.type_with([], key)), plain)
            self.assertEqual(self.symname(self.type_with(["RALT"], key)), fn)


if __name__ == "__main__":
    unittest.main()
