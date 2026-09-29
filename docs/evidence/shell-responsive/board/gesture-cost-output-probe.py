import json, os, subprocess, time, datetime
from pathlib import Path
os.environ.update(XDG_RUNTIME_DIR="/run/shell", SWAYSOCK="/run/shell/sway-ipc.sock")
since=datetime.datetime.now(datetime.timezone.utc).isoformat()
def ipc(command):
    start=time.monotonic()
    result=subprocess.run(["swaymsg","-r",command],capture_output=True,text=True,timeout=10,check=True)
    rows=json.loads(result.stdout)
    if not all(row.get("success") for row in rows): raise RuntimeError(command+": "+result.stdout)
    return {"command":command,"ipc_wall_ms":round((time.monotonic()-start)*1000,2)}
output=json.loads(subprocess.run(["swaymsg","-t","get_outputs","-r"],capture_output=True,text=True,check=True).stdout)[0]
width,height=output["rect"]["width"],output["rect"]["height"]
x,y=width//2,height-20
commands=[]
try:
    ipc("card_shell benchmark-stop")
    ipc("card_shell back")
    ipc("card_shell benchmark injected")
    commands.append(ipc(f"card_shell down 94 {x} {y}"))
    for i in range(1,17):
        commands.append(ipc(f"card_shell motion 94 {x} {y-i*height//80}"))
        time.sleep(.025)
    commands.append(ipc("card_shell up 94"))
    time.sleep(1)
finally:
    ipc("card_shell back")
    ipc("card_shell benchmark-stop")
raw=subprocess.run(["journalctl","-b","-u","shell","--since",since,"--no-pager","-o","cat"],capture_output=True,text=True,check=True).stdout
keep=[line for line in raw.splitlines() if any(tag in line for tag in ["K230_CARD_BENCH ","K230_CARD_SHELL repaint-cost ","K230_CARD_SHELL input-cost ","K230_CARD_SHELL frame-damage "])]
Path("/run/k230-gesture-cost.log").write_text("\n".join(keep)+"\n")
Path("/run/k230-gesture-cost.json").write_text(json.dumps({"source_revision":"27066809", "evidence_class":"physical-board-injected-input", "logical_output":[width,height], "transform":output["transform"], "started_at":since,"events":commands},indent=2)+"\n")
print("K230_GESTURE_COST_CAPTURED",len(keep))
