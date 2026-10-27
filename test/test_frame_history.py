import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from meerk40t.camera.frame_web import Station

class HistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); r=self.root
        (r/'outline.json').write_text(json.dumps({'paths':[[[0,0],[10,10]]]}))
        (r/'job.lmc').write_text('fixture')
        self.job=dict(path=str(r/'job.lmc'),sha256=hashlib.sha256(b'fixture').hexdigest(),approval_id='original',shift=[0,0],label='Test',summary='2 passes',passes=2,pause_between_layers=True,mark_speed=500,runner='fake',module_dir='fake')
        self.design=dict(label='Test',outline=str(r/'outline.json'),rect=[0,0,10,10],settings={'passes':2},cut_job=self.job)
        (r/'catalog.json').write_text(json.dumps({'designs':{'original':self.design}}))
        self.cfg=dict(self.design,design_id='original',designs_file=str(r/'catalog.json'),records=str(r),data_dir=str(r),ui_state=str(r/'ui.json'))
        self.s=Station(self.cfg)
        self.run='web-cut-'+'a'*32
        self.s.cut_marker(self.job).write_text(json.dumps(dict(run_id=self.run,job=self.job)))
        self.control=r/self.run/'layer-control'; self.control.mkdir(parents=True)
        self.control.joinpath('state.json').write_text(json.dumps(dict(phase='complete',completed=2,total=2)))
        for n in (1,2):
            (r/f'fill-{self.run}-p{n}.jsonl').write_text('\n'.join(json.dumps(e) for e in [dict(event='cleanup',errors=[]),dict(event='stop_disable_commands_attempted',controller_completion_seen=True)]))
    def request(self):
        return dict(action='prepare_repeat',design_id='original',confirm_job_sha256=self.job['sha256'])
    def test_repeat_preserves_records_and_does_not_execute(self):
        old=self.s.cut_marker(self.job).read_bytes()
        with patch('meerk40t.camera.frame_web.subprocess.Popen') as popen:
            result=self.s.action(self.request()); popen.assert_not_called()
        self.assertTrue(result['cut']['available'])
        self.assertNotEqual(result['design_id'],'original')
        self.assertEqual(self.s.cut_marker(self.job).read_bytes(),old)
        self.assertFalse(self.s.cut_marker(self.s.config['cut_job']).exists())
        self.assertTrue(Station(self.cfg).cut_status()['available'])
        with self.assertRaises(ValueError): self.s.action(self.request())
    def test_missing_cleanup_or_failed_batch_blocks_repeat(self):
        (self.root/f'fill-{self.run}-p2.jsonl').unlink()
        self.assertFalse(self.s.history()[0]['repeatable'])
        with self.assertRaises(ValueError): self.s.action(self.request())
    def test_changed_position_draft_hash_and_running_block(self):
        self.s.dx=1
        with self.assertRaises(ValueError): self.s.action(self.request())
        self.s.dx=0;self.s.draft={'passes':3}
        with self.assertRaises(ValueError): self.s.action(self.request())
        self.s.draft=None;(self.root/'job.lmc').write_text('changed')
        with self.assertRaises(ValueError): self.s.action(self.request())
        self.s.process=Mock();self.s.process.poll.return_value=None
        with self.assertRaises(ValueError): self.s.action(self.request())
    def test_select_clears_previous_progress(self):
        self.s.log_path=self.root/'old.log';self.s.control_dir=self.control
        self.s.action(dict(action='select_design',design_id='original'))
        self.assertIsNone(self.s.log_path);self.assertIsNone(self.s.control_dir)
