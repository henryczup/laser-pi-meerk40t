"""Bounded one-shot commissioning of the exact MeerK40t-exported test.
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
parser.add_argument("--run-id", help="Unique record name; existing records must never be removed")
parser.add_argument("--execute-approved-single-test", action="store_true")
args = parser.parse_args()
BASE = args.data_dir.resolve()
if args.execute_approved_single_test and (not args.run_id or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", args.run_id)):
    parser.error("Execution requires a unique alphanumeric --run-id")
JOB=BASE.parent/'jobs/commissioning_10mm_square.lmc'
COR=BASE/'Henry-UV-200mm-nonlinear-only.cor'
assert hashlib.sha256(JOB.read_bytes()).hexdigest()=='8dc43a7aa93f4a78686223306a06a955d337f36c5ef62c10f99d615ee91a04b2'
assert hashlib.sha256(COR.read_bytes()).hexdigest()=='7527534eabab8cf0ff6960a50355e25ac605f30184a67f66f80b5b2010a9cd22'
names={v:k for k,v in list_command_lookup.items()}
commands=[]
for line in JOB.read_text().splitlines():
 parts=line.split();commands.append((names[parts[0]],*[int(v,16) for v in parts[1:]]))
assert len(commands)==20 and all(len(c)==6 for c in commands)
assert sum(c[0]==0x8005 for c in commands)==6
assert commands[-1]==(0x8002,0,0,0,0,0)
assert {c[1] for c in commands if c[0]==0x800a}=={83}
assert {c[1] for c in commands if c[0]==0x800b}=={20}
assert {c[1] for c in commands if c[0]==0x800c}=={188}
for c in commands:
 if c[0] in (0x8001,0x8005):
  assert 31421<=c[1]<=34115 and 31293<=c[2]<=34243
table=object.__new__(GalvoController)._read_correction_file(str(COR))
packet=b''.join(struct.pack('<6H',*c) for c in commands)
packet+=struct.pack('<6H',0x8002,0,0,0,0,0)*(256-len(commands))
assert len(packet)==3072 and len(table)==4225
print('PASS exact job/calibration hashes, six mark segments, 10mm bounds, fixed source recipe.',flush=True)
if not args.execute_approved_single_test:raise SystemExit(0)

import usb.core,usb.util
logfile=BASE/('commissioning-square-'+args.run_id+'.jsonl')
marker=BASE/('commissioning-square-'+args.run_id+'.started')
# An interrupted command must never be automatically repeated.
with marker.open('x') as f:f.write(datetime.datetime.now(datetime.timezone.utc).isoformat())
log=logfile.open('x')
def event(name,**data):
 row={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'event':name,**data}
 log.write(json.dumps(row)+'\n');log.flush();print(json.dumps(row),flush=True)
d=None;initialized=False;execute_sent=False;complete=False
deadline=time.monotonic()+30
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
 assert d.write(2,packet,timeout=1000)==3072
 cmd(0x19,0)
 event('single_job_loaded',mark_segments=6)
 # One and only one ExecuteList command. No retries after any uncertain result.
 execute_sent=True
 cmd(5)
 cmd(0x16,1);cmd(0x1d,2000,20,1);cmd(0x21,0)
 event('execute_sent')
 time.sleep(.3)
 status=wait_idle()
 marktime=cmd(0x41,3)
 complete=True
 event('controller_returned_idle',status=status[3],mark_time_words=marktime,physical_mark_requires_user_inspection=True)
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
