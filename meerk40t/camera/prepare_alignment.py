"""Prepare a private, translated red-frame candidate offline. Never controls hardware."""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def prepare(source, rect, shift, evidence, output_dir):
    source, evidence = Path(source).resolve(), Path(evidence).resolve()
    output_dir = Path(output_dir).resolve()
    repo = Path(__file__).resolve().parents[2]
    if output_dir == repo or repo in output_dir.parents:
        raise ValueError('Keep alignment artifacts outside the repository')
    if len(rect) != 4 or len(shift) != 2 or not all(math.isfinite(v) for v in (*rect, *shift)):
        raise ValueError('Expected finite rectangle and translation')
    x, y, w, h = rect
    dx, dy = shift
    if not (0 <= x < x+w <= 200 and 0 <= y < y+h <= 200):
        raise ValueError('Original rectangle outside 200mm field')
    if not (0 <= x+dx < x+dx+w <= 200 and 0 <= y+dy < y+dy+h <= 200):
        raise ValueError('Translated rectangle outside 200mm field')
    raw = source.read_bytes()
    paths = json.loads(raw)['paths']
    if not isinstance(paths, list) or not 1 <= len(paths) <= 20:
        raise ValueError('Expected 1–20 paths')
    translated = []
    for path in paths:
        if not 2 <= len(path) <= 2000:
            raise ValueError('Invalid path length')
        new_path = []
        for point in path:
            if len(point) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in point):
                raise ValueError('Invalid point')
            px, py = point
            if not (x <= px <= x+w and y <= py <= y+h):
                raise ValueError('Original outline outside rectangle')
            new_path.append([px+dx, py+dy])
        translated.append(new_path)
    image_bytes = evidence.read_bytes()
    # Each trial gets its own directory. Never replace prior evidence or records.
    output_dir.mkdir(parents=True, exist_ok=False)
    outline = output_dir / 'outline.json'
    outline.write_text(json.dumps({'description': 'Red-frame alignment candidate only',
                                  'paths': translated}, indent=2), encoding='utf-8')
    record = {
        'status': 'unverified_frame_candidate',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'original_outline': str(source),
        'original_sha256': hashlib.sha256(raw).hexdigest(),
        'original_rect_mm': list(rect), 'translation_from_original_mm': list(shift),
        'frame_rect_mm': [x+dx, y+dy, w, h],
        'outline': str(outline),
        'outline_sha256': hashlib.sha256(outline.read_bytes()).hexdigest(),
        'before_image': str(evidence),
        'before_image_sha256': hashlib.sha256(image_bytes).hexdigest(),
        'cut_approved': False,
    }
    (output_dir / 'candidate.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-outline', required=True)
    parser.add_argument('--original-rect', nargs=4, type=float, required=True)
    parser.add_argument('--shift', nargs=2, type=float, required=True,
                        help='Total X Y translation from the ORIGINAL, never the last trial')
    parser.add_argument('--before-image', required=True)
    parser.add_argument('--output-dir', required=True, help='New private trial directory')
    args = parser.parse_args()
    print(json.dumps(prepare(args.original_outline, args.original_rect, args.shift,
                             args.before_image, args.output_dir), indent=2))


if __name__ == '__main__':
    main()
