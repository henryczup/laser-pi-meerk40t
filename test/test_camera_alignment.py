import json
import tempfile
import unittest
from pathlib import Path

from meerk40t.camera.prepare_alignment import prepare


class TestAlignmentPreparation(unittest.TestCase):
    def test_translation_preserves_original_and_previous_trial(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / 'original.json'
            original.write_text(json.dumps({'paths': [[[49.5, 0], [150.5, 120]]]}))
            before = original.read_bytes()
            evidence = root / 'evidence.jpg'
            evidence.write_bytes(b'private evidence fixture')
            first = prepare(original, [49.5, 0, 101, 120], [18, 0], evidence, root/'trial1')
            second = prepare(original, [49.5, 0, 101, 120], [27, 0], evidence, root/'trial2')
            self.assertEqual(second['frame_rect_mm'], [76.5, 0, 101, 120])
            self.assertEqual(json.loads(Path(second['outline']).read_text())['paths'][0][0], [76.5, 0])
            self.assertEqual(original.read_bytes(), before)
            self.assertFalse(first['cut_approved'])
            with self.assertRaises(FileExistsError):
                prepare(original, [49.5, 0, 101, 120], [27, 0], evidence, root/'trial2')
            with self.assertRaises(ValueError):
                prepare(original, [49.5, 0, 101, 120], [51, 0], evidence, root/'invalid')
            self.assertFalse((root/'invalid').exists())
