"""Read-only progress from verified batch completion messages; no hardware access."""
import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def batch_progress(log_text, manifest):
    total = manifest['passes']
    required = {}
    for index, job in enumerate(manifest['jobs'], 1):
        required.setdefault(job['card'], set()).add(index)
    completed = {card: {} for card in required}
    current = None
    for line in log_text.splitlines():
        match = re.fullmatch(r'(START|COMPLETED) pass (\d+)/(\d+) card (\d+) part (\d+)', line)
        if not match:
            continue
        event, layer, count, card, part = match.groups()
        layer, count, card, part = map(int, (layer, count, card, part))
        if count != total or not 1 <= layer <= total or part not in required.get(card, set()):
            continue
        if event == 'START':
            current = dict(layer=layer, card=card)
        else:
            completed[card].setdefault(layer, set()).add(part)
    cards = [dict(card=card, completed=sum(parts == required[card] for parts in layers.values()))
             for card, layers in sorted(completed.items())]
    return dict(total=total, cards=cards, current=current,
                complete=all(c['completed'] == total for c in cards))


def single_job_progress(log_text, total):
    done = set()
    current = None
    for line in log_text.splitlines():
        match = re.fullmatch(r'(START|COMPLETED) additional pass (\d+)/(\d+)', line)
        if match:
            kind, layer, count = match.groups()
            layer, count = int(layer), int(count)
            if count == total and 1 <= layer <= total:
                current = dict(layer=layer, card=1)
                if kind == 'COMPLETED': done.add(layer)
    if total == 1:
        events = []
        for line in log_text.splitlines():
            try: events.append(json.loads(line))
            except ValueError: pass
        if any(e.get('event') == 'execute_attempted' for e in events): current = dict(layer=1, card=1)
        if (any(e.get('controller_completion_seen') is True for e in events)
            and any(e.get('event') == 'cleanup' and e.get('errors') == [] for e in events)
            and not any(e.get('event') == 'error' for e in events)): done.add(1)
    return dict(total=total, cards=[dict(card=1, completed=len(done))], current=current,
                complete=len(done) == total)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8082)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get('Host', '').split(':')[0] not in ('localhost', '127.0.0.1'):
                self.send_error(403); return
            if self.path != '/progress':
                self.send_error(404); return
            try:
                payload = json.dumps(batch_progress(args.log.read_text(errors='replace'), manifest)).encode()
                self.send_response(200)
            except (OSError, ValueError):
                payload = b'{"error":"Progress unavailable"}'
                self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Access-Control-Allow-Origin', 'http://127.0.0.1:8085')
            self.end_headers()
            self.wfile.write(payload)
        def log_message(self, *args):
            pass
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()

if __name__ == '__main__':
    main()
