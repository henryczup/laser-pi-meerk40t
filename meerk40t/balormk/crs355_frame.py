"""Bounded scanner-only frame with an independently enabled red pointer.

UV emission must be physically disabled. Never enables laser output, writes a
GPIO port, uploads a marking list or invokes ExecuteList. Default is offline.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import time

from meerk40t.balormk.controller import GalvoController

COR_HASH = '7527534eabab8cf0ff6960a50355e25ac605f30184a67f66f80b5b2010a9cd22'
ALLOWED = {2: 0, 7: 0, 9: 0, 14: 0, 31: 0, 18: 0, 21: 1, 16: 3, 13: 4}


def packet(op, *args):
    if op not in ALLOWED or len(args) != ALLOWED[op]:
        raise ValueError('Command is not permitted in scanner-only framing')
    if any(not isinstance(a, int) or not 0 <= a <= 65535 for a in args):
        raise ValueError('Invalid command word')
    if op == 21 and args != (1,):
        raise ValueError('Only correction table enable is allowed')
    if op == 16 and args[2] not in (0, 1):
        raise ValueError('Invalid correction-table marker')
    return struct.pack('<6H', op, *args, *([0] * (5-len(args))))


def rectangle(x, y, width, height, scale_x, scale_y, step_mm=2):
    if not math.isfinite(step_mm) or not 0.5 <= step_mm <= 10:
        raise ValueError('Step must be between 0.5 and 10mm')
    values = (x, y, width, height, scale_x, scale_y)
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Non-finite framing geometry')
    if not (0 <= x < x+width <= 200 and 0 <= y < y+height <= 200):
        raise ValueError('Rectangle must fit the calibrated 200mm field')
    if not (0 < scale_x <= 2 and 0 < scale_y <= 2):
        raise ValueError('Invalid calibration scales')
    corners = [(x,y), (x+width,y), (x+width,y+height), (x,y+height), (x,y)]
    points = []
    for a, b in zip(corners, corners[1:]):
        count = math.ceil(math.dist(a,b)/step_mm)
        for i in range(count):
            px = a[0]+(b[0]-a[0])*i/count
            py = a[1]+(b[1]-a[1])*i/count
            native = (round(32768+(py-100)*65535/200*scale_y),
                      round(32768+(px-100)*65535/200*scale_x))
            if not all(0 <= v <= 65535 for v in native):
                raise ValueError('Native point out of bounds')
            points.append(native)
    return points


def trace(send, points, seconds, clock=time.monotonic, sleep=time.sleep, interval=0.005):
    if not math.isfinite(interval) or not 0 <= interval <= 0.02:
        raise ValueError('Interval must be between zero and 20ms')
    if not math.isfinite(seconds) or not 0 < seconds <= 60:
        raise ValueError('Frame duration must be 0–60 seconds')
    deadline = clock()+seconds
    previous = (32768,32768)
    try:
        send(31)  # StopExecute
        send(2)   # DisableLaser
        send(14)  # LaserSignalOff
        send(18)  # ResetList; never execute a stale marking list
        while clock() < deadline:
            for x,y in points:
                if clock() >= deadline:
                    break
                distance = min(65535, round(math.dist(previous, (x,y))))
                send(13, x, y, 0, distance)
                previous = (x,y)
                sleep(interval)
    finally:
        errors = []
        for op in (31, 2, 14):
            try:
                send(op)
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError('Framing cleanup failed: '+ '; '.join(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--rect', nargs=4, type=float, default=[49.5,40,101,120],
                        metavar=('X','Y','WIDTH','HEIGHT'))
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--fast', action='store_true',
                        help='5mm steps without intentional delay for faster red refresh')
    parser.add_argument('--execute-red-frame', action='store_true')
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 60:
        parser.error('seconds must be greater than zero and at most 60')
    base = args.data_dir.resolve()
    cfg = json.loads((base/'current-lightburn-JCZFiber.json').read_text())['Settings']
    if cfg['RedLightPortBit'] != -1:
        raise ValueError('This runner requires an independently enabled pointer')
    points = rectangle(*args.rect, cfg['Galvo_2_Scale'], cfg['Galvo_1_Scale'],
                       step_mm=5 if args.fast else 2)
    cor = base/'Henry-UV-200mm-nonlinear-only.cor'
    if hashlib.sha256(cor.read_bytes()).hexdigest() != COR_HASH:
        raise ValueError('Correction file hash mismatch')
    table = GalvoController._read_correction_file(object.__new__(GalvoController), str(cor))
    if len(table) != 4225:
        raise ValueError('Correction table length mismatch')
    for x,y in points:
        packet(13,x,y,0,0)
    print(json.dumps({'offline_validated': True, 'rect_mm': args.rect,
                      'seconds': args.seconds, 'points':len(points),
                      'red_pointer_scale_alignment': 'not physically verified'}), flush=True)
    if not args.execute_red_frame:
        return
    import fcntl
    import usb.core
    import usb.util
    with (base/'red-frame.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        dev = usb.core.find(idVendor=0x9588, idProduct=0x9899)
        if dev is None:
            raise RuntimeError('Controller missing')
        def send(op, *values, read=True):
            if dev.write(2, packet(op,*values), timeout=1000) != 12:
                raise IOError('Short USB write')
            if read:
                return struct.unpack('<4H', bytes(dev.read(0x88,8,timeout=1000)))
        try:
            usb.util.claim_interface(dev,0)
            identity = json.loads((base/'controller-identity.json').read_text())['queries']
            version, serial = send(7), send(9)
            if list(version[:3]) != identity['version']['words'][:3] or list(serial[:3]) != identity['serial']['words'][:3]:
                raise RuntimeError('Controller identity mismatch')
            if version[3]&4:
                raise RuntimeError('Controller busy; no framing started')
            send(2)
            send(14)
            send(21,1)
            for index,(x,y) in enumerate(table):
                send(16,x,y,int(index!=0),read=False)
            print('RED FRAME STARTED: UV disabled; scanner-only moves',flush=True)
            trace(send,points,args.seconds,interval=0 if args.fast else 0.005)
            print('RED FRAME STOPPED: stop/disable/signal-off acknowledged',flush=True)
        finally:
            usb.util.dispose_resources(dev)


if __name__ == '__main__':
    main()
