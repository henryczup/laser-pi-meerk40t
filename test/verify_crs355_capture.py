"""No USB objects or hardware connections are created by these tests."""
from pathlib import Path
import json,struct
from types import SimpleNamespace
from meerk40t.balormk.crs355 import CRS355Controller as HenryUVController
from meerk40t.balormk.crs355 import calibrated_view as transform
import argparse, hashlib
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--data-dir", type=Path, required=True)
a = parser.parse_args()
# These scales are read from the external station adapter, not distributed.
import runpy
legacy = runpy.run_path(str(a.data_dir / 'henry_uv_compat.py'))
def calibrated_view(view):
    transform(view, legacy['SX'], legacy['SY'])
from meerk40t.core.view import View
from meerk40t.core.units import Length
b=a.data_dir.resolve()
c=object.__new__(HenryUVController)
c.service=SimpleNamespace(mock=True,source='uv',default_frequency=120,default_power=120,default_speed=500,power_invert=False,signal_updates=False)
c.service.corfile = str(b/'Henry-UV-200mm-nonlinear-only.cor')
c.service.crs355_cor_sha256 = '7527534eabab8cf0ff6960a50355e25ac605f30184a67f66f80b5b2010a9cd22'
c.usb_log=lambda *a:None
c.serial_number_found=None
singles=[]
c._command=lambda *args,**kwargs:singles.append(list(args)) or (0,0,0,0x20)
c.init_laser()
rows=[v for v in singles if v[0]==0x10]
expected=json.loads((b/'lightburn-correction-capture.json').read_text())
assert [r[1:3] for r in rows]==[r[:2] for r in expected]
assert [r[3] for r in rows]==[0]+[1]*4224
expected_init=[[9],[7],[3],[0x15,1],[4],[0x16,0],[0x1b,1],[0x17,1],[0x1c,1],[0x1d,2000,20,1],[0x1a,200],[0x1e,3],[6,3],[0x23,0],[0x32,0,82,1000,24],[0x3a,0],[0x21,0],[0x22,3275],[0xd,32768,32768]]
assert [v for v in singles if v[0]!=0x10]==expected_init
print('PASS startup/control words and all4225 correction entries')
commands=[]
c._list_write=lambda op,*args:commands.append([op,*args]+[0]*(5-len(args)))
for attr in ('_frequency','_power','_fpk','_travel_speed','_speed','_delay_on','_delay_off','_delay_poly'):
 setattr(c,attr,None)
c.set_settings({'frequency':120,'power':120,'speed':500})
job=json.loads((b/'capture-1792075279.jsonl.jobs.json').read_text())[0]
assert commands==job[1:9],(commands,job[1:9])
print('PASS all eight source/speed/timing commands match LightBurn job prefix')
v=View('200mm','200mm',native_scale_x=float(Length('200mm'))/65535,native_scale_y=float(Length('200mm'))/65535)
calibrated_view(v)
coords=lambda x,y:tuple(round(z) for z in v.position(f'{x}mm',f'{y}mm'))
expected_segments={tuple(sorted((coords(x,y),coords(x2,y2)))) for x,y,x2,y2 in json.loads((b/'offline-grid-points.json').read_text())}
segments=set();last=None
for cmd in job:
 if cmd[0]==0x8001:last=tuple(cmd[1:3])
 if cmd[0]==0x8005:segments.add(tuple(sorted((last,tuple(cmd[1:3])))));last=tuple(cmd[1:3])
assert expected_segments==segments
print('PASS all18 grid endpoints')
c.service.mock=False
try:c.connect_if_needed()
except ConnectionRefusedError:pass
else:raise AssertionError('Live output guard failed')
print('PASS live connection blocked pending physical validation')
