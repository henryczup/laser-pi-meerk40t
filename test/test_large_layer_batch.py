import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from meerk40t.camera import layer_batch
class TestLargeLayerBatch(unittest.TestCase):
    def run_fake(self,n,fail_at=None):
        with tempfile.TemporaryDirectory() as d:
            control=Path(d)/'control';calls=[]
            def launch(cmd):
                calls.append(cmd[cmd.index('--run-id')+1])
                return Mock(wait=Mock(return_value=1 if len(calls)==fail_at else 0))
            argv=['batch','--child-runner','fake.py','--passes',str(n),'--control-dir',str(control),'--data-dir',d,'--run-id','bounded','--execute-approved-fill']
            with patch('sys.argv',argv),patch.object(layer_batch.signal,'signal'),patch.object(layer_batch.subprocess,'Popen',side_effect=launch),patch.object(layer_batch,'completed',return_value=True),patch('builtins.print'):
                if fail_at:
                    with self.assertRaisesRegex(RuntimeError,'no repeat'):layer_batch.main()
                else:self.assertEqual(layer_batch.main(),0)
            return calls,json.loads((control/'state.json').read_text())
    def test_99_passes_unique_records(self):
        calls,state=self.run_fake(99)
        self.assertEqual(calls,['bounded-p'+str(i) for i in range(1,100)])
        self.assertEqual(state['completed'],99);self.assertEqual(state['phase'],'complete')
    def test_failure_stops_remaining_without_retry(self):
        calls,state=self.run_fake(99,3)
        self.assertEqual(calls,['bounded-p1','bounded-p2','bounded-p3'])
        self.assertEqual(state['completed'],2);self.assertEqual(state['phase'],'failed')
    def test_reject_101(self):
        with patch('sys.argv',['batch','--child-runner','fake','--passes','101','--control-dir','unused']),patch('sys.stderr'):
            with self.assertRaises(SystemExit):layer_batch.main()
