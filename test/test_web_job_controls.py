import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from meerk40t.camera.frame_web import Station, Handler
from meerk40t.camera.svg_upload import save_svg
from meerk40t.camera import layer_batch


class JobControlsTest(unittest.TestCase):
    def test_tailnet_host_and_origin_are_explicit(self):
        handler = object.__new__(Handler)
        handler.server = Mock()
        handler.server.station.config = {'allowed_hosts':['pi.example.ts.net']}
        handler.headers = {'Host':'pi.example.ts.net', 'Origin':'http://pi.example.ts.net'}
        self.assertTrue(handler.valid_host())
        self.assertTrue(handler.valid_origin())
        handler.headers['Origin'] = 'https://attacker.example'
        self.assertFalse(handler.valid_origin())
        handler.headers['Host'] = 'attacker.example'
        self.assertFalse(handler.valid_host())

    def test_simple_batch_progress_does_not_count_partial_layer(self):
        from meerk40t.camera.batch_progress import single_job_progress
        result = single_job_progress('START additional pass 1/2\nCOMPLETED additional pass 1/2\nSTART additional pass 2/2',2)
        self.assertEqual(result['cards'][0]['completed'],1)
        self.assertFalse(result['complete'])

    def test_svg_archive_and_reject_active_content(self):
        with tempfile.TemporaryDirectory() as d:
            good = '<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="20mm"><path d="M0 0L1 1"/></svg>'
            record = save_svg(d, '../../design.svg', good)
            self.assertEqual(record['name'], 'design.svg')
            self.assertFalse(record['cut_approved'])
            self.assertEqual(Path(record['path']).read_text(), good)
            for bad in ('<!DOCTYPE svg>'+good, '<svg><script/></svg>', '<svg onload="x"/>',
                        '<svg><image href="https://example.com"/></svg>', '<svg><path style="fill:url(#x)"/></svg>'):
                with self.assertRaises(ValueError):
                    save_svg(d, 'bad.svg', bad)

    def test_upload_invalidates_cut_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            shape = root/'shape.json'
            shape.write_text(json.dumps({'paths': [[[0,0],[10,10]]]}))
            design = dict(label='test', outline=str(shape), rect=[0,0,10,10], cut_job=dict(
                shift=[0,0], sha256='fixture', label='test', summary='test'))
            catalog = root/'catalog.json'
            catalog.write_text(json.dumps({'designs': {'a': design}}))
            cfg = dict(design, designs_file=str(catalog), design_id='a', records=str(root/'records'), ui_state=str(root/'ui.json'))
            station = Station(cfg)
            station.action(dict(action='upload_svg', name='new.svg', svg='<svg><rect width="5" height="5"/></svg>'))
            self.assertFalse(station.cut_status()['available'])
            self.assertFalse(Station(cfg).cut_status()['available'])
            station.process = Mock()
            station.process.poll.return_value = None
            with self.assertRaises(ValueError):
                station.action(dict(action='upload_svg', name='other.svg', svg='<svg/>'))

    def test_pause_does_not_signal_usb_or_child(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); shape = root/'shape.json'
            shape.write_text(json.dumps({'paths': [[[0,0],[10,10]]]}))
            station = Station(dict(outline=str(shape), rect=[0,0,10,10], records=d))
            station.process = Mock(); station.process.poll.return_value = None
            station.kind = 'cut'; station.control_dir = root/'control'; station.control_dir.mkdir()
            station.action({'action':'pause'})
            self.assertTrue((station.control_dir/'pause').exists())
            station.process.send_signal.assert_not_called()
            station.action({'action':'continue'})
            self.assertFalse((station.control_dir/'pause').exists())

    def test_batch_pauses_after_cleanup_then_continues_without_repeating(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); control = root/'control'; child = root/'fake.py'
            child.write_text('''import sys,json,time
from pathlib import Path
a=sys.argv; root=Path(a[a.index('--data-dir')+1]); name=a[a.index('--run-id')+1]
(root/(name+'.entered')).touch()
while not (root/'release').exists(): time.sleep(.02)
(root/('fill-'+name+'.jsonl')).write_text('\\n'.join(json.dumps(e) for e in [{'event':'cleanup','errors':[]},{'event':'stop_disable_commands_attempted','controller_completion_seen':True}]))
''')
            process = subprocess.Popen([sys.executable, layer_batch.__file__, '--child-runner', str(child),
                '--passes','2','--control-dir',str(control),'--data-dir',d,'--run-id','test',
                '--execute-approved-fill'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            def wait_for(predicate):
                end = time.monotonic()+10
                while not predicate():
                    if time.monotonic()>end: self.fail('Timed out')
                    time.sleep(.02)
            try:
                wait_for(lambda: (root/'test-p1.entered').exists())
                (control/'pause').touch(); (root/'release').touch()
                wait_for(lambda: (control/'state.json').exists() and json.loads((control/'state.json').read_text()).get('phase')=='paused')
                self.assertFalse((root/'test-p2.entered').exists())
                (control/'pause').unlink()
                out, err = process.communicate(timeout=10)
                self.assertEqual(process.returncode, 0, err)
                self.assertEqual(out.count(b'START additional pass 1/2'), 1)
                self.assertEqual(json.loads((control/'state.json').read_text())['completed'], 2)
            finally:
                if process.poll() is None: process.kill(); process.communicate()

    def test_missing_cleanup_is_not_completion(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'run.jsonl'
            p.write_text(json.dumps({'event':'stop_disable_commands_attempted','controller_completion_seen':True}))
            self.assertFalse(layer_batch.completed(p))
