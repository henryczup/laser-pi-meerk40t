"""Validate and archive SVG preparation requests; never interpret laser commands."""
import hashlib
import json
import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_SVG_BYTES = 1024 * 1024


def save_svg(records, name, content):
    if not isinstance(name, str) or not name.lower().endswith('.svg'):
        raise ValueError('Choose an SVG file')
    if not isinstance(content, str) or not 0 < len(content.encode('utf-8')) <= MAX_SVG_BYTES:
        raise ValueError('SVG must be between 1 byte and 1 MB')
    if re.search(r'<!\s*(DOCTYPE|ENTITY)', content, re.I):
        raise ValueError('SVG document types and entities are not supported')
    root = ET.fromstring(content)
    allowed = {'svg', 'g', 'path', 'rect', 'circle', 'ellipse', 'line', 'polyline',
               'polygon', 'defs', 'clipPath', 'title', 'desc', 'metadata'}
    if root.tag != '{http://www.w3.org/2000/svg}svg' and root.tag != 'svg':
        raise ValueError('Expected an SVG document')
    count = 0
    for element in root.iter():
        count += 1
        if count > 20000:
            raise ValueError('SVG contains too many elements')
        tag = element.tag.rsplit('}', 1)[-1]
        if tag not in allowed:
            raise ValueError('Unsupported SVG element: ' + tag + '. Convert text to paths and remove images/scripts.')
        for key, value in element.attrib.items():
            key = key.rsplit('}', 1)[-1].lower()
            if key.startswith('on') or key in ('href', 'src') or re.search(r'url\s*\(|@import|javascript:', value, re.I):
                raise ValueError('SVG links, events and external resources are not supported')
    directory = Path(records) / ('svg-' + uuid.uuid4().hex)
    directory.mkdir(parents=True, exist_ok=False)
    raw = content.encode('utf-8')
    (directory / 'source.svg').write_bytes(raw)
    record = dict(name=Path(name.replace('\\', '/')).name[:160], path=str(directory / 'source.svg'),
                  sha256=hashlib.sha256(raw).hexdigest(), width=root.get('width'),
                  height=root.get('height'), viewBox=root.get('viewBox'),
                  status='needs_toolpath_preparation', cut_approved=False)
    (directory / 'request.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return record
