"""Local-only camera, red framing, and explicitly configured single-pass jobs."""
import argparse
import hashlib
import os
import re
import json
import math
import secrets
import signal
import subprocess
import threading
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def translated(original, rect, dx, dy):
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (dx, dy, *rect)):
        raise ValueError('Coordinates must be finite numbers')
    x, y, w, h = rect
    bounds = [x+dx, y+dy, w, h]
    if not (0 <= x+dx < x+dx+w <= 200 and 0 <= y+dy < y+dy+h <= 200):
        raise ValueError('Frame would leave the 200 mm field')
    paths = []
    for path in original['paths']:
        result = []
        for px, py in path:
            if not (math.isfinite(px) and math.isfinite(py) and x <= px <= x+w and y <= py <= y+h):
                raise ValueError('Original outline outside original frame')
            result.append([px+dx, py+dy])
        paths.append(result)
    return bounds, {'paths': paths}


class Station:
    def __init__(self, config, enabled=False):
        self.config = config
        self.original = json.loads(Path(config['outline']).read_text())
        self.dx, self.dy = config.get('initial_shift', [0, 0])
        self.enabled = enabled
        self.process = None
        self.guard = threading.Lock()
        self.message = 'Ready to adjust candidate; no frame started'
        self.failed = False
        self.log = None
        self.log_path = None
        self.kind = 'frame'
        self.design_id = config.get('design_id', 'current')
        self.draft = None
        self.upload = None
        self.control_dir = None
        translated(self.original, config['rect'], self.dx, self.dy)
        state_path = config.get('ui_state')
        if state_path and Path(state_path).exists():
            saved = json.loads(Path(state_path).read_text())
            design = self.catalog().get(saved['design_id'])
            if design and saved.get('definition_sha256') == hashlib.sha256(json.dumps(design, sort_keys=True).encode()).hexdigest():
                self.select_design(saved['design_id'])
                translated(self.original, self.config['rect'], *saved['shift'])
                self.dx, self.dy = saved['shift']
                self.draft = saved.get('draft')
                self.upload = saved.get('upload')

    def persist_ui(self):
        if not self.config.get('ui_state'):
            return
        path = Path(self.config['ui_state'])
        definition = self.catalog()[self.design_id]
        data = dict(design_id=self.design_id, shift=[self.dx,self.dy], draft=self.draft, upload=self.upload,
                    definition_sha256=hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest())
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, indent=2))
        temporary.replace(path)

    def status(self):
        if self.process is not None and self.process.poll() is not None:
            code = self.process.returncode
            self.log.close()
            log_text = self.log_path.read_text(errors='replace')
            if self.kind == 'cut' and code == 0 and '"controller_completion_seen": true' in log_text and 'cleanup_error' not in log_text:
                self.message = 'Prepared job finished; controller completion recorded. Inspect the result.'
                # Notifications are optional and cannot affect job execution/retry.
                try:
                    try:
                        from meerk40t.camera.completion_email import queue
                    except ImportError:
                        from completion_email import queue
                    queue(self.config.get('completion_email'), self.log_path,
                          self.config.get('cut_job', {}).get('label', 'Prepared job'))
                except Exception:
                    pass
            elif self.kind == 'frame' and code == 0 and 'RED FRAME STOPPED' in log_text:
                self.message = 'Frame finished; cleanup acknowledged'
            else:
                self.failed = True
                self.message = 'Operation interrupted or failed. Inspect log before another run: ' + str(self.log_path)
            self.process = None
        return dict(dx=self.dx, dy=self.dy, running=self.process is not None,
                    message=self.message, enabled=self.enabled, failed=self.failed,
                    cut=self.cut_status(), design_id=self.design_id,
                    designs=[dict(id=k, label=v['label']) for k,v in self.catalog().items()],
                    settings=self.draft or self.config.get('settings', {}),
                    settings_pending=self.draft is not None, upload=self.upload,
                    layer_control=self.layer_status())

    def catalog(self):
        if self.config.get('designs_file'):
            return json.loads(Path(self.config['designs_file']).read_text())['designs']
        return {self.design_id: dict(label=self.config.get('cut_job', {}).get('label', 'Current design'))}

    def select_design(self, design_id):
        designs = self.catalog()
        if design_id not in designs:
            raise ValueError('Unknown prepared design')
        design = designs[design_id]
        original = json.loads(Path(design['outline']).read_text())
        shift = design.get('initial_shift', [0, 0])
        translated(original, design['rect'], *shift)
        updated = dict(self.config)
        for key in ('outline', 'rect', 'initial_shift', 'settings', 'cut_job'):
            updated.pop(key, None)
            if key in design:
                updated[key] = design[key]
        self.config = updated
        self.original, self.dx, self.dy = original, *shift
        self.design_id, self.draft = design_id, None
        self.upload = None
        self.message = 'Loaded ' + design['label'] + '. Verify placement before running.'

    def save_settings(self, values):
        limits = dict(speed_mm_s=(1,10000), interval_mm=(.005,5),
                      uv_duty_percent=(0,100), frequency_khz=(10,150), passes=(1,20))
        if not isinstance(values, dict) or set(values) != set(limits):
            raise ValueError('Provide speed, interval, UV duty, frequency and passes')
        for name, (low,high) in limits.items():
            value = values[name]
            if isinstance(value, bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError('Invalid '+name)
        if int(values['passes']) != values['passes']:
            raise ValueError('Pass count must be an integer')
        directory = Path(self.config['records']) / ('settings-' + uuid.uuid4().hex)
        directory.mkdir(parents=True, exist_ok=False)
        (directory/'request.json').write_text(json.dumps(dict(design_id=self.design_id,
            original_outline=self.config['outline'], shift=[self.dx,self.dy],
            settings=values, status='needs_toolpath_preparation', cut_approved=False), indent=2))
        self.draft = dict(values)
        self.message = 'Settings saved for preparation. Rebuild and validate the toolpath before Run. ' + str(directory)

    def cut_status(self):
        job = self.config.get('cut_job')
        if not job:
            return dict(available=False, reason='No reviewed cutting job loaded')
        reason = job.get('blocked_reason', '')
        if self.draft is not None:
            reason = 'Edited settings need a rebuilt, validated toolpath before running.'
        if [self.dx, self.dy] != job['shift']:
            reason = 'Frame offset differs from prepared cut. Regenerate and review the job.'
        if self.upload is not None:
            reason = 'Uploaded SVG needs a prepared, validated toolpath. Previous design cannot run.'
        marker = self.cut_marker(job)
        if marker.exists():
            reason = 'This prepared pass has already been requested. Review its record before another pass.'
        return dict(available=not bool(reason), reason=reason, label=job['label'],
                    summary=job['summary'], sha256=job['sha256'])

    def cut_marker(self, job):
        approval = job.get('approval_id', job['sha256'])
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', approval):
            raise ValueError('Invalid job approval record')
        return Path(self.config['records']) / ('cut-' + approval + '.requested')

    def start_cut(self, request):
        state = self.cut_status()
        if not state['available']:
            raise ValueError(state['reason'])
        job = self.config['cut_job']
        if request.get('confirm_job_sha256') != job['sha256']:
            raise ValueError('Confirm the displayed single-pass job before starting')
        if hashlib.sha256(Path(job['path']).read_bytes()).hexdigest() != job['sha256']:
            raise ValueError('Prepared job hash changed')
        if job['mark_speed'] not in (500, 1000, 2000, 4000):
            raise ValueError('Unsupported reviewed speed')
        run_id = 'web-cut-' + uuid.uuid4().hex
        directory = Path(self.config['records']) / run_id
        directory.mkdir(parents=True, exist_ok=False)
        command = [self.config['python'], '-u', job['runner'], '--data-dir', self.config['data_dir'],
                   '--job', job['path'], '--job-sha256', job['sha256'],
                   '--mark-speed', str(job['mark_speed'])]
        self.control_dir = None
        if job.get('pause_between_layers'):
            passes = job.get('passes')
            if isinstance(passes, bool) or not isinstance(passes, int) or not 1 <= passes <= 20:
                raise ValueError('Invalid prepared layer count')
            self.control_dir = directory / 'layer-control'
            command = [self.config['python'], '-u', str(Path(__file__).with_name('layer_batch.py')),
                       '--child-runner', job['runner'], '--passes', str(passes),
                       '--control-dir', str(self.control_dir)] + command[3:]
        env = dict(os.environ, PYTHONPATH=job['module_dir'])
        check = subprocess.run(command, env=env, capture_output=True, timeout=20)
        (directory/'validation.log').write_bytes(check.stdout + check.stderr)
        if check.returncode:
            raise ValueError('Cut validation failed; see ' + str(directory))
        marker = self.cut_marker(job)
        # Exclusive durable record protects against double-clicks, reconnects and restarts.
        with marker.open('x') as stream:
            json.dump(dict(run_id=run_id, job=job, shift=[self.dx, self.dy]), stream)
        self.kind = 'cut'
        self.log_path = directory/'cut.log'
        self.log = self.log_path.open('xb')
        try:
            self.process = subprocess.Popen(command + ['--run-id', run_id, '--execute-approved-fill'],
                                            env=env, stdout=self.log, stderr=subprocess.STDOUT)
        except Exception:
            self.log.close()
            self.failed = True
            raise
        self.message = 'Prepared job requested. No automatic repeat.'

    def layer_status(self):
        supported = bool(self.process is not None and self.kind == 'cut' and self.control_dir)
        state = {}
        if self.control_dir and (self.control_dir / 'state.json').exists():
            state = json.loads((self.control_dir / 'state.json').read_text())
        pending = bool(self.control_dir and (self.control_dir / 'pause').exists())
        return dict(supported=supported, pause_requested=pending, **state)

    def pause_layers(self, pause):
        state = self.layer_status()
        if not state['supported'] or not self.control_dir.is_dir():
            raise ValueError('This job does not support layer-boundary pause')
        if state.get('phase') in ('complete', 'stopped', 'failed'):
            raise ValueError('This batch has ended')
        marker = self.control_dir / 'pause'
        if pause:
            marker.touch(exist_ok=True)
            self.message = 'Pause requested: the current layer finishes first. Stop interrupts immediately.'
        else:
            marker.unlink(missing_ok=True)
            self.message = 'Continuing remaining layers'

    def action(self, request):
        with self.guard:
            state = self.status()
            action = request.get('action')
            if action == 'stop':
                if self.process is not None:
                    self.process.send_signal(signal.SIGINT)
                    self.message = 'Stop requested; awaiting process exit and cleanup review'
                return self.status()
            if action in ('pause', 'continue'):
                self.pause_layers(action == 'pause')
                return self.status()
            if state['running']:
                raise ValueError('Wait for the current frame to stop before changing placement')
            if self.failed:
                raise ValueError('Previous run needs inspection; further framing is locked')
            if action == 'upload_svg':
                try:
                    from meerk40t.camera.svg_upload import save_svg
                except ImportError:
                    from svg_upload import save_svg
                self.upload = save_svg(self.config['records'], request.get('name'), request.get('svg'))
                self.message = 'SVG saved for preparation: ' + self.upload['name']
            elif action == 'select_design':
                self.select_design(request.get('design_id'))
            elif action == 'settings':
                self.save_settings(request.get('settings'))
            elif action == 'cut':
                self.start_cut(request)
            elif action == 'nudge':
                axis, amount = request.get('axis'), request.get('amount')
                if axis not in ('x', 'y') or amount not in (-10, -1, -.1, .1, 1, 10):
                    raise ValueError('Invalid nudge')
                dx = round(self.dx + (amount if axis == 'x' else 0), 6)
                dy = round(self.dy + (amount if axis == 'y' else 0), 6)
                translated(self.original, self.config['rect'], dx, dy)
                self.dx, self.dy = dx, dy
                self.message = 'Candidate updated. Click Frame to project it.'
            elif action in ('save', 'frame'):
                if self.upload is not None:
                    raise ValueError('Uploaded SVG needs a prepared framing outline first')
                if action == 'frame' and not self.enabled:
                    raise ValueError('Live framing is not enabled')
                bounds, outline = translated(self.original, self.config['rect'], self.dx, self.dy)
                directory = Path(self.config['records']) / uuid.uuid4().hex
                directory.mkdir(parents=True, exist_ok=False)
                outline_path = directory/'outline.json'
                outline_path.write_text(json.dumps(outline))
                (directory/'candidate.json').write_text(json.dumps(dict(
                    original_outline=self.config['outline'], original_rect=self.config['rect'],
                    translation_from_original_mm=[self.dx, self.dy], frame_rect_mm=bounds,
                    status='unverified_frame_candidate', cut_approved=False), indent=2))
                if action == 'save':
                    self.message = 'Candidate saved: ' + str(directory)
                else:
                    command = [self.config['python'], '-u', '-m', 'meerk40t.balormk.crs355_frame',
                               '--data-dir', self.config['data_dir'], '--rect', *map(str, bounds),
                               '--outline-json', str(outline_path), '--fast', '--until-stopped']
                    # Offline validation first; never retry execution.
                    check = subprocess.run(command, capture_output=True, timeout=20)
                    (directory/'validation.log').write_bytes(check.stdout + check.stderr)
                    if check.returncode:
                        raise ValueError('Offline validation failed; see ' + str(directory))
                    self.log_path = directory/'frame.log'
                    self.kind = 'frame'
                    self.log = self.log_path.open('wb')
                    try:
                        self.process = subprocess.Popen(command + ['--execute-red-frame'],
                                                        stdout=self.log, stderr=subprocess.STDOUT)
                    except Exception:
                        self.log.close()
                        raise
                    self.message = 'Framing - press Stop to finish'
            else:
                raise ValueError('Unknown action')
            if action in ('settings', 'select_design', 'nudge', 'upload_svg'):
                self.persist_ui()
            return self.status()


class Handler(BaseHTTPRequestHandler):
    def reply(self, body, content_type='application/json', status=200):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Frame-Options', 'DENY')
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        allowed = {'127.0.0.1', 'localhost'} | set(self.server.station.config.get('allowed_hosts', []))
        return self.headers.get('Host', '').split(':')[0].lower() in allowed

    def valid_origin(self):
        origin = self.headers.get('Origin')
        if origin is None:
            return True
        from urllib.parse import urlsplit
        parsed = urlsplit(origin)
        return parsed.scheme in ('http', 'https') and parsed.netloc == self.headers.get('Host', '')

    def do_GET(self):
        if not self.valid_host():
            self.send_error(403)
            return
        try:
            route = self.path.split('?')[0]
            if route == '/':
                page = Path(__file__).with_name('frame_web.html').read_text(encoding='utf-8')
                self.reply(page.replace('__TOKEN__', self.server.token).encode(), 'text/html; charset=utf-8')
            elif route == '/progress':
                try:
                    from meerk40t.camera.batch_progress import batch_progress, single_job_progress
                except ImportError:
                    from batch_progress import batch_progress, single_job_progress
                station = self.server.station
                job = station.config.get('cut_job')
                if not job:
                    self.reply(b'{"error":"No batch run"}', status=404)
                    return
                log_path = station.log_path if station.kind == 'cut' else None
                if log_path is None:
                    marker = station.cut_marker(job)
                    if not marker.exists():
                        self.reply(b'{"error":"No batch run"}', status=404)
                        return
                    run_id = json.loads(marker.read_text())['run_id']
                    if not re.fullmatch(r'web-cut-[a-f0-9]{32}', run_id):
                        raise ValueError('Invalid run record')
                    log_path = Path(station.config['records']) / run_id / 'cut.log'
                text = log_path.read_text(errors='replace')
                if Path(job['path']).suffix == '.lmc':
                    progress = single_job_progress(text, station.config.get('settings', {}).get('passes', 1))
                else:
                    manifest = json.loads(Path(job['path']).read_text())
                    progress = batch_progress(text, manifest)
                self.reply(json.dumps(progress).encode())
            elif route == '/status':
                with self.server.station.guard:
                    self.reply(json.dumps(self.server.station.status()).encode())
            elif route == '/snapshot.jpg':
                with urllib.request.urlopen('http://127.0.0.1:8080/snapshot.jpg', timeout=10) as response:
                    self.reply(response.read(12*1024*1024), 'image/jpeg')
            else:
                self.send_error(404)
        except Exception as error:
            self.reply(json.dumps({'error': str(error)}).encode(), status=503)

    def do_POST(self):
        if not self.valid_host() or not self.valid_origin() or self.headers.get('X-Frame-Token') != self.server.token:
            self.send_error(403)
            return
        if self.path != '/action':
            self.send_error(404)
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 2 * 1024 * 1024:
                raise ValueError('Invalid request size')
            result = self.server.station.action(json.loads(self.rfile.read(size)))
            self.reply(json.dumps(result).encode())
        except Exception as error:
            self.reply(json.dumps({'error': str(error)}).encode(), status=400)

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--port', type=int, default=8081)
    parser.add_argument('--enable-red-framing', action='store_true')
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.station = Station(json.loads(Path(args.config).read_text()), args.enable_red_framing)
    server.token = secrets.token_urlsafe(32)
    stop = threading.Event()
    if server.station.config.get('completion_email', {}).get('enabled'):
        try:
            from meerk40t.camera.completion_email import watch
        except ImportError:
            from completion_email import watch
        threading.Thread(target=watch, args=(server.station, stop), daemon=True).start()
    try:
        server.serve_forever()
    finally:
        stop.set()


if __name__ == '__main__':
    main()
