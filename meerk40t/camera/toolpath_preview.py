"""Read-only preview of a hash-matched CRS command file. Never contacts hardware."""
import hashlib
import json
import math
from pathlib import Path


def preview(job, data_dir):
    if not job or Path(job['path']).suffix.lower() != '.lmc':
        raise ValueError('Animation requires a prepared LMC job')
    path = Path(job['path'])
    if path.stat().st_size > 6 * 1024 * 1024:
        raise ValueError('Job too large for preview')
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != job['sha256']:
        raise ValueError('Job hash mismatch; preview withheld')
    settings = json.loads((Path(data_dir) / 'current-lightburn-JCZFiber.json').read_text())['Settings']
    sx, sy = float(settings['Galvo_2_Scale']), float(settings['Galvo_1_Scale'])
    if not all(math.isfinite(s) and s > 0 for s in (sx, sy)):
        raise ValueError('Invalid preview calibration')
    previous = [100., 100.]
    segments = []
    for line in raw.decode('utf-8').splitlines():
        fields = line.split()
        if not fields or fields[0] not in ('listJumpTo', 'listMarkTo'):
            continue
        if len(fields) != 6:
            raise ValueError('Malformed motion command')
        words = [int(v, 16) for v in fields[1:]]
        if any(not 0 <= v <= 65535 for v in words):
            raise ValueError('Invalid motion word')
        a, b = words[:2]
        point = [100 + (b-32768)*200/65535/sx, 100 + (a-32768)*200/65535/sy]
        segments.append(previous + point + [fields[0] == 'listMarkTo'])
        previous = point
        if len(segments) > 40000:
            raise ValueError('Too many preview moves')
    if not any(s[4] for s in segments):
        raise ValueError('No engraving strokes found')
    speed = float(job.get('mark_speed', 500))
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError('Invalid marking speed')
    return dict(label=job.get('label', 'Prepared job'), sha256=digest,
                segments=segments, mark_speed=speed, travel_speed=4000,
                passes=job.get('passes', 1), field_mm=200)
