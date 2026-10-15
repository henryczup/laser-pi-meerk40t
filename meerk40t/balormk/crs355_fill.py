"""Bounded one-shot execution of an explicitly hash-approved CRS fill job.
Default is offline validation only. Never changes the saved mock profile.
"""
from pathlib import Path
import json,hashlib,struct,time,sys,datetime
from meerk40t.balormk.controller import GalvoController,list_command_lookup
from meerk40t.balormk.crs355 import INITIALIZE_AFTER_COR
import argparse, re
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--data-dir", type=Path, required=True,
                    help="Existing station reference directory, preserving identity and run history")
parser.add_argument("--job", type=Path, required=True)
parser.add_argument("--job-sha256", required=True)
parser.add_argument("--run-id", help="Unique record name; existing records must never be removed")
parser.add_argument("--execute-approved-fill", action="store_true")
args = parser.parse_args()
if not __debug__:raise RuntimeError('Do not run hardware tools with Python -O')
BASE = args.data_dir.resolve()
if args.execute_approved_fill and (not args.run_id or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", args.run_id)):
    parser.error("Execution requires a unique alphanumeric --run-id")
JOB=args.job.resolve()
COR=BASE/'Henry-UV-200mm-nonlinear-only.cor'
if hashlib.sha256(JOB.read_bytes()).hexdigest()!=args.job_sha256:raise ValueError('Job hash mismatch')
assert hashlib.sha256(COR.read_bytes()).hexdigest()=='7527534eabab8cf0ff6960a50355e25ac605f30184a67f66f80b5b2010a9cd22'
names={v:k for k,v in list_command_lookup.items()}
commands=[]
for line in JOB.read_text().splitlines():
 parts=line.split();commands.append((names[parts[0]],*[int(v,16) for v in parts[1:]]))
expected_prefix=[(0x8051,0,0,0,0,0),(0x800a,83,0,0,0,0),
 (0x801e,17,17,0,0,0),(0x800b,20,0,0,0,0),(0x8006,1508,0,0,0,0),
 (0x800c,188,0,0,0,0),(0x8007,100,0,0,0,0),(0x8008,100,0,0,0,0),
 (0x800f,10,0,0,0,0)]
if commands[:9]!=expected_prefix:raise ValueError('Recipe prefix mismatch')
if commands[-2:]!=[(0x8004,10,0,0,0,0),(0x8002,0,0,0,0,0)]:raise ValueError('Invalid ending')
body=commands[9:-2]
if not 0<len(body)<=60000 or len(body)%3:raise ValueError('Invalid fill sequence')
for i in range(0,len(body),3):
 delay,jump,mark=body[i:i+3]
 if delay not in [(0x800d,20,0,0,0,0),(0x800d,40,0,0,0,0)]:raise ValueError('Invalid jump delay')
 if jump[0]!=0x8001 or mark[0]!=0x8005:raise ValueError('Expected independent jump/mark strokes')
 for c in (jump,mark):
  if len(c)!=6 or c[3]!=0 or c[5]!=0 or any(not 0<=v<=65535 for v in c):raise ValueError('Invalid movement')
mark_count=len(body)//3
table=object.__new__(GalvoController)._read_correction_file(str(COR))
from meerk40t.balormk.crs355_stream import packets, stream
blocks=packets(commands)
if len(table)!=4225:raise ValueError('Invalid correction length')
print(f'PASS hash-approved fill: {mark_count} strokes, {len(blocks)} packets, fixed recipe.',flush=True)
if not args.execute_approved_fill:raise SystemExit(0)

import usb.core,usb.util
import fcntl
hardware_lock=(BASE/'red-frame.lock').open('a')
fcntl.flock(hardware_lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
logfile=BASE/('fill-'+args.run_id+'.jsonl')
marker=BASE/('fill-'+args.run_id+'.started')
# An interrupted command must never be automatically repeated.
with marker.open('x') as f:f.write(datetime.datetime.now(datetime.timezone.utc).isoformat())
log=logfile.open('x')
def event(name,**data):
 row={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'event':name,**data}
 log.write(json.dumps(row)+'\n');log.flush();print(json.dumps(row),flush=True)
d=None;initialized=False;execute_sent=False;complete=False
deadline=time.monotonic()+1800
def cmd(op,*args,read=True,cleanup=False):
 if not cleanup and time.monotonic()>deadline:raise TimeoutError('Overall commissioning deadline reached')
 data=struct.pack('<6H',op,*args,*([0]*(5-len(args))))
 assert d.write(2,data,timeout=1000)==12
 if read:return struct.unpack('<4H',bytes(d.read(0x88,8,timeout=1000)))
def wait_idle(seconds=5):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  words=cmd(7)
  if words[3]&32 and not words[3]&4:return words
  time.sleep(.02)
 raise TimeoutError('Controller did not return ready/idle')
try:
 d=usb.core.find(idVendor=0x9588,idProduct=0x9899)
 if d is None:raise RuntimeError('Controller missing')
 usb.util.claim_interface(d,0)
 version=cmd(7);serial=cmd(9)
 identity=json.loads((BASE/'controller-identity.json').read_text())
 assert list(version[:3])==identity['queries']['version']['words'][:3],'Controller version mismatch'
 assert list(serial[:3])==identity['queries']['serial']['words'][:3],'Controller identity mismatch'
 if version[3]&4:raise RuntimeError('Controller busy: test not started')
 event('identity_verified',status=version[3])
 initialized=True
 cmd(3);cmd(0x15,1)
 for i,(x,y) in enumerate(table):cmd(0x10,x,y,0 if i==0 else 1,read=False)
 event('correction_uploaded',entries=len(table))
 for c in INITIALIZE_AFTER_COR:cmd(*c)
 cmd(0x12);cmd(0x21,0)
 wait_idle()
 event('fill_validated',mark_segments=mark_count,job_sha256=args.job_sha256)
 # May execute during streaming; never retry an ambiguous transport failure.
 execute_sent=True
 stream(blocks,cmd,lambda block:d.write(2,block,timeout=1000),event,timeout=1700)
 complete=True
except BaseException as exc:
 event('error',error=repr(exc),execute_may_have_been_sent=execute_sent)
 raise
finally:
 if d is not None and initialized:
  for op,args in [(0x1f,()),(2,()),(0x21,(0,))]:
   try:cmd(op,*args,cleanup=True)
   except Exception as exc:event('cleanup_error',command=op,error=repr(exc))
  event('stop_disable_commands_attempted',controller_completion_seen=complete)
 if d is not None:usb.util.dispose_resources(d)
 log.close()
