"""Private CSI camera preview; access through SSH forwarding, no laser control."""
import io
import json
import math
import time
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

lock = threading.Lock()
applied_controls = None
controls_file = Path(__file__).with_name('camera-controls.json')


def validate_controls(values):
    bounds = {'ExposureValue': (-8, 8), 'ExposureTime': (100, 200000),
              'AnalogueGain': (1, 8), 'Brightness': (-1, 1), 'Contrast': (0, 4)}
    for key, value in values.items():
        if key == 'AeEnable':
            if not isinstance(value, bool):
                raise ValueError('AeEnable must be boolean')
        elif key not in bounds or not isinstance(value, (int, float)) or not math.isfinite(value) or not bounds[key][0] <= value <= bounds[key][1]:
            raise ValueError('Invalid camera control')
    return values


def apply_controls():
    global applied_controls
    if controls_file.exists():
        values = validate_controls(json.loads(controls_file.read_text()))
        if values != applied_controls:
            camera.set_controls(values)
            applied_controls = values
            time.sleep(0.7)



class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] == "/snapshot.jpg":
            with lock:
                apply_controls()
                output = io.BytesIO()
                camera.capture_file(output, format="jpeg")
                body = output.getvalue()
            content_type = "image/jpeg"
        elif self.path == '/metadata':
            with lock:
                body = json.dumps(camera.capture_metadata(), default=str).encode()
            content_type = 'application/json'
        elif self.path == "/":
            body = b'''<!doctype html><title>Laser Pi camera</title>
<style>body{background:#151515;color:white;font:18px sans-serif}img{max-width:100%;max-height:90vh}</style>
<p>Pi 4 camera preview | Live view only</p><img id="view" src="/snapshot.jpg">
<script>const v=document.getElementById('view');v.onload=()=>setTimeout(()=>v.src='/snapshot.jpg?t='+Date.now(),500);</script>'''
            content_type = "text/html; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    # Import and open hardware only on explicit invocation, never on import.
    import argparse
    from picamera2 import Picamera2
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    global camera
    camera = Picamera2()
    try:
        camera.configure(camera.create_still_configuration(main={"size": (1640, 1232)}))
        camera.start()
        ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
    finally:
        camera.stop()
        camera.close()


if __name__ == "__main__":
    main()
