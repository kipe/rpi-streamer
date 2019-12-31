import os
import io
import json
import shutil
import fnmatch
import picamera
import logging
import subprocess
import socketserver
from datetime import datetime
from threading import Condition
from http import server
from jinja2 import Environment, FileSystemLoader, select_autoescape

HTTP_PORT = int(os.environ.get('HTTP_PORT', '80'))
RESOLUTION = os.environ.get('RESOLUTION', '640x480')
FRAMERATE = int(os.environ.get('FRAMERATE', 24))
ROTATION = int(os.environ.get('ROTATION', 0))

if ROTATION not in [0, 90, 180, 270]:
    ROTATION = 0


class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)


class StreamingHandler(server.BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.jinja_environment = Environment(
            loader=FileSystemLoader(self.template_paths),
            autoescape=select_autoescape(['html', 'xml'])
        )

        super().__init__(*args, **kwargs)

    @property
    def template_paths(self):
        return [os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates')]

    def annotate_camera(self):
        self.server.camera.annotate_background = picamera.Color('black')
        self.server.camera.annotate_text = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%SZ')

    def do_GET(self):
        if self.path == '/':
            width, height = RESOLUTION.split('x') if ROTATION in [0, 180] else list(reversed(RESOLUTION.split('x')))
            content = self.jinja_environment.get_template('index.html').render(
                width=width,
                height=height,
            )

            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
            return

        if self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    self.annotate_camera()
                    with self.server.output.condition:
                        self.server.output.condition.wait()
                        frame = self.server.output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
            return

        if self.path == '/api/capture':
            content = '[]'
            if os.path.exists('/data/capture'):
                content = json.dumps([
                    {
                        'filename': filename,
                        'link': '/api/capture/%s' % (filename),
                        'size': os.stat(os.path.join('/data/capture', filename)).st_size,
                    }
                    for filename in sorted(os.listdir('/data/capture'))
                ])
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
            return

        if fnmatch.fnmatch(self.path, '/api/capture/*.jpg'):
            filepath = os.path.join('/data/capture/', self.path.split('/')[-1])

            if not os.path.exists(filepath):
                self.send_error(404)
                self.end_headers()
                return

            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Content-Length', os.stat(filepath).st_size)
            self.end_headers()
            with open(filepath, 'rb') as content:
                shutil.copyfileobj(content, self.wfile)
            return

        self.send_error(404)
        self.end_headers()

    def do_POST(self):
        if self.path == '/api/capture':
            if not os.path.exists('/data/capture'):
                os.makedirs('/data/capture')

            filename = '%s.jpg' % (datetime.utcnow().isoformat())

            self.server.camera.capture('/data/capture/%s' % (filename), use_video_port=True)
            content = '{"status": "ok", "filename": "%s"}' % (filename)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
            return

        self.send_error(404)
        self.end_headers()

    def do_DELETE(self):
        if fnmatch.fnmatch(self.path, '/api/capture/*.jpg'):
            filepath = os.path.join('/data/capture/', self.path.split('/')[-1])

            if not os.path.exists(filepath):
                self.send_error(404)
                self.end_headers()
                return

            os.remove(filepath)
            self.send_response(204)
            self.end_headers()
            return

        self.send_error(404)
        self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address=('', HTTP_PORT), handler=StreamingHandler):
        subprocess.call(['modprobe', 'bcm2835-v4l2'])

        self.output = StreamingOutput()
        self.camera = picamera.PiCamera(resolution='%s' % RESOLUTION, framerate=FRAMERATE)
        self.camera.rotation = ROTATION

        self.camera.start_recording(self.output, format='mjpeg')

        super(StreamingServer, self).__init__(address, handler)


if __name__ == '__main__':
    try:
        server = StreamingServer()
        print('Starting camera server')
        server.serve_forever()
    except Exception as e:
        print(str(e))
    print('Stopping camera server')
