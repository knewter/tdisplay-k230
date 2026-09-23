"""Actual Wayland virtual keyboard for headless focus-return checks.

Wire requests follow pinned wlroots protocol/virtual-keyboard-unstable-v1.xml.
Only a synthetic key is sent, and no user key data is read or recorded.
"""
import array
import os
import socket
import struct
import time

class Keyboard:
    def __init__(self, path):
        self.socket=socket.socket(socket.AF_UNIX)
        self.socket.settimeout(10)
        self.socket.connect(str(path))
        self.serial=2
        self.globals={}
        self.send(1,1,struct.pack('=I',2)) # wl_display.get_registry
        self.roundtrip()
        self.bind('zwp_virtual_keyboard_manager_v1',4)
        self.bind('wl_seat',5)
        self.send(4,0,struct.pack('=II',5,6))
        self.serial=6
        keymap=b'''xkb_keymap {
xkb_keycodes "probe" { minimum=8; maximum=255; <AC01>=38; };
xkb_types "probe" { type "ONE_LEVEL" { modifiers=None; map[None]=Level1; level_name[Level1]="Any"; }; };
xkb_compatibility "probe" {};
xkb_symbols "probe" { key <AC01> { type="ONE_LEVEL", [ a ] }; };
};\0'''
        fd=os.memfd_create('card-test-keymap',os.MFD_CLOEXEC)
        try:
            os.write(fd,keymap)
            self.send(6,0,struct.pack('=II',1,len(keymap)),fd)
        finally: os.close(fd)
        self.roundtrip()

    def send(self,obj,opcode,payload=b'',fd=None):
        message=struct.pack('=II',obj,((len(payload)+8)<<16)|opcode)+payload
        if fd is None: self.socket.sendall(message)
        else:
            sent=self.socket.sendmsg([message],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[fd]))])
            assert sent==len(message)

    def read(self,n):
        data=b''
        while len(data)<n:
            chunk=self.socket.recv(n-len(data))
            assert chunk,'Wayland test connection closed'
            data+=chunk
        return data

    def roundtrip(self):
        self.serial+=1
        callback=self.serial
        self.send(1,0,struct.pack('=I',callback))
        while True:
            obj,size_op=struct.unpack('=II',self.read(8))
            size,opcode=size_op>>16,size_op&0xffff
            payload=self.read(size-8)
            assert not (obj==1 and opcode==0),('Wayland protocol error',payload)
            if obj==2 and opcode==0:
                name,length=struct.unpack('=II',payload[:8])
                interface=payload[8:8+length-1].decode()
                self.globals[interface]=name
            if obj==callback and opcode==0: return

    def bind(self,interface,obj):
        encoded=interface.encode()+b'\0'
        padded=encoded+b'\0'*((-len(encoded))%4)
        self.send(2,0,struct.pack('=II',self.globals[interface],len(encoded))+padded+struct.pack('=II',1,obj))

    def press(self):
        stamp=int(time.monotonic()*1000)&0xffffffff
        self.send(6,1,struct.pack('=III',stamp,30,1))
        self.send(6,1,struct.pack('=III',stamp,30,0))
        self.roundtrip()

    def close(self):
        self.socket.close()
