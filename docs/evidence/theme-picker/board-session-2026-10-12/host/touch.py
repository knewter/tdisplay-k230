import importlib.util,sys
spec=importlib.util.spec_from_file_location("p","/root/tmp/k230-theme-board-session-20261012/theme-picker-profile.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
dev=[p.parent.parent.name for p in __import__("pathlib").Path("/sys/class/input").glob("event*/device/name") if p.read_text().strip()==m.DEVICE_NAME and str(p.resolve()).startswith("/sys/devices/virtual/input/")]
assert len(dev)==1
m.native_touch("/dev/input/"+dev[0],*[int(v) for v in sys.argv[1:]])
