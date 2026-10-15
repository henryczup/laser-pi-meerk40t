"""Private CSI camera preview; access through SSH forwarding, no laser control."""
import io
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] == "/snapshot.jpg":
            with lock:
                output = io.BytesIO()
                camera.capture_file(output, format="jpeg")
                body = output.getvalue()
            content_type = "image/jpeg"
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
