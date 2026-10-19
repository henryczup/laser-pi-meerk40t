import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from meerk40t.camera.check_pi import capture, ssh_command


class TestCameraCheck(unittest.TestCase):
    def test_fresh_capture(self):
        data = io.BytesIO()
        Image.new('RGB', (16, 12)).save(data, 'JPEG')
        def runner(command, **kwargs):
            self.assertEqual(kwargs['timeout'], 25)
            return subprocess.CompletedProcess(command, 0, data.getvalue(), b'')
        with tempfile.TemporaryDirectory() as directory:
            first, manifest = capture(['ssh'], directory, 'example', runner)
            second, _ = capture(['ssh'], directory, 'example', runner)
            self.assertEqual(first['status'], 'captured')
            self.assertEqual(first['width'], 16)
            self.assertTrue(manifest.exists())
            self.assertNotEqual(first['image'], second['image'])

    def test_failures_never_return_stale_image(self):
        for response in (subprocess.CompletedProcess([], 255, b'', b'unreachable'),
                         subprocess.CompletedProcess([], 0, b'<html>error</html>', b'')):
            with tempfile.TemporaryDirectory() as directory:
                record, manifest = capture([], directory, 'example', lambda *a, **k: response)
                self.assertEqual(record['status'], 'failed')
                self.assertNotIn('image', record)
                self.assertFalse(list(Path(directory).glob('*.jpg')))
                self.assertTrue(manifest.exists())

    def test_timeout(self):
        def runner(*args, **kwargs):
            raise subprocess.TimeoutExpired('ssh', 25)
        with tempfile.TemporaryDirectory() as directory:
            record, _ = capture([], directory, 'example', runner)
            self.assertEqual(record['status'], 'failed')

    def test_strict_read_only_command(self):
        command = ssh_command('pi.local', 'user', 'key', 'hosts')
        self.assertIn('StrictHostKeyChecking=yes', command)
        self.assertIn('BatchMode=yes', command)
        self.assertIn('/snapshot.jpg', command[-1])
        with self.assertRaises(ValueError):
            ssh_command('-evil', 'user', 'key', 'hosts')
