import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from meerk40t.camera.frame_web import Station, translated


class TestFrameWeb(unittest.TestCase):
    def test_design_switch_and_pending_settings_survive_restart(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root/'source.json'
            source.write_text(json.dumps({'paths': [[[0, 0], [10, 10]]]}))
            design = dict(label='Design A', outline=str(source), rect=[0,0,10,10], initial_shift=[0,0],
                          settings=dict(speed_mm_s=500,interval_mm=.025,uv_duty_percent=12,frequency_khz=120,passes=1))
            catalog = root/'designs.json'
            catalog.write_text(json.dumps({'designs': {'a':design,'b':dict(design,label='Design B')}}))
            config = dict(design, records=str(root/'records'), designs_file=str(catalog),
                          design_id='a', ui_state=str(root/'ui.json'))
            station = Station(config)
            station.action(dict(action='select_design',design_id='b'))
            edits = dict(design['settings'],interval_mm=.05)
            station.action(dict(action='settings',settings=edits))
            restarted = Station(config)
            self.assertEqual(restarted.design_id,'b')
            self.assertEqual(restarted.draft,edits)
            self.assertFalse(restarted.cut_status()['available'])
            with self.assertRaises(ValueError):
                restarted.action(dict(action='settings',settings=dict(edits,passes=1.5)))
            with self.assertRaises(ValueError):
                restarted.action(dict(action='select_design',design_id='../../arbitrary'))

    def test_cut_guards_and_persistent_single_request(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root/'source.json'
            source.write_text(json.dumps({'paths': [[[0, 0], [10, 10]]]}))
            jobfile = root/'job.lmc'
            jobfile.write_bytes(b'fixture')
            digest = hashlib.sha256(jobfile.read_bytes()).hexdigest()
            job = dict(path=str(jobfile), sha256=digest, shift=[0, 0], label='test',
                       summary='one pass', mark_speed=1000, runner='runner.py', module_dir=d,
                       blocked_reason='Identity mismatch')
            config = dict(outline=str(source), rect=[0, 0, 10, 10], records=str(root/'records'),
                          python='python', data_dir=d, cut_job=job)
            station = Station(config)
            with patch('subprocess.run') as validate, patch('subprocess.Popen') as start:
                request = dict(action='cut', confirm_job_sha256=digest)
                with self.assertRaises(ValueError):
                    station.action(request)
                job['blocked_reason'] = ''
                station.dx = 1
                with self.assertRaises(ValueError):
                    station.action(request)
                station.dx = 0
                with self.assertRaises(ValueError):
                    station.action(dict(action='cut'))
                start.assert_not_called()
                validate.return_value.returncode = 0
                validate.return_value.stdout = validate.return_value.stderr = b''
                start.return_value.poll.return_value = None
                station.action(request)
                self.assertIn('--execute-approved-fill', start.call_args[0][0])
                self.assertNotIn('--execute-approved-fill', validate.call_args[0][0])
                with self.assertRaises(ValueError):
                    station.action(request)
                station.log.close()
                restarted = Station(config)
                self.assertFalse(restarted.cut_status()['available'])
                with self.assertRaises(ValueError):
                    restarted.action(request)
                self.assertEqual(start.call_count, 1)

    def test_bounds_and_no_scaling(self):
        shape = {'paths': [[[49.5, 0], [150.5, 120]]]}
        rect, moved = translated(shape, [49.5, 0, 101, 120], 27, 0)
        self.assertEqual(rect, [76.5, 0, 101, 120])
        self.assertEqual(moved['paths'][0][1], [177.5, 120])
        for dx, dy in ((60, 0), (0, -1), (float('nan'), 0)):
            with self.assertRaises(ValueError):
                translated(shape, [49.5, 0, 101, 120], dx, dy)

    def test_nudge_save_and_live_gate(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            outline = root/'source.json'
            outline.write_text(json.dumps({'paths': [[[49.5, 0], [150.5, 120]]]}))
            station = Station(dict(outline=str(outline), rect=[49.5, 0, 101, 120],
                                   records=str(root/'records'), initial_shift=[27, 0]))
            with patch('subprocess.Popen') as process:
                station.action(dict(action='nudge', axis='x', amount=.1))
                self.assertEqual(station.dx, 27.1)
                with self.assertRaises(ValueError):
                    station.action(dict(action='nudge', axis='y', amount=-1))
                self.assertEqual(station.dy, 0)
                station.action(dict(action='save'))
                record = json.loads(next((root/'records').glob('*/candidate.json')).read_text())
                self.assertFalse(record['cut_approved'])
                with self.assertRaises(ValueError):
                    station.action(dict(action='frame'))
                process.assert_not_called()

    def test_run_is_bounded_and_stop_is_not_retry(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root/'source.json'
            source.write_text(json.dumps({'paths': [[[0, 0], [10, 10]]]}))
            station = Station(dict(outline=str(source), rect=[0, 0, 10, 10],
                                   records=str(root/'records'), python='python', data_dir=d), True)
            with patch('subprocess.run') as validate, patch('subprocess.Popen') as start:
                validate.return_value.returncode = 0
                validate.return_value.stdout = validate.return_value.stderr = b''
                start.return_value.poll.return_value = None
                station.action(dict(action='frame'))
                command = start.call_args[0][0]
                self.assertIn('--execute-red-frame', command)
                self.assertIn('--until-stopped', command)
                self.assertNotIn('--execute-red-frame', validate.call_args[0][0])
                with self.assertRaises(ValueError):
                    station.action(dict(action='nudge', axis='x', amount=1))
                station.action(dict(action='stop'))
                start.return_value.send_signal.assert_called_once()
                self.assertEqual(start.call_count, 1)
                station.log.close()
