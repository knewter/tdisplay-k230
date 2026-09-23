import ctypes,json,platform
class Pair(ctypes.Structure):
    _fields_=[("key",ctypes.c_int64),("value",ctypes.c_uint64)]
p=Pair(4,0)
lib=ctypes.CDLL(None,use_errno=True)
lib.syscall.restype=ctypes.c_long
result=lib.syscall(ctypes.c_long(258),ctypes.byref(p),ctypes.c_size_t(1),ctypes.c_size_t(0),ctypes.c_void_p(),ctypes.c_uint(0))
print(json.dumps({"kernel":platform.release(),"syscall":258,"result":result,"errno":ctypes.get_errno(),"key":p.key,"value":p.value,"rvv_advertised":result==0 and p.key==4 and bool(p.value&4)}))
