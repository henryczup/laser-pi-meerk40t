import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from meerk40t.balormk.runlog import RunLog
from meerk40t.balormk.crs355_stream import stream


class BrokenConsole:
    def write(self, text):
        raise BrokenPipeError('SSH reader gone')


class TestRunLog(unittest.TestCase):
    def test_console_loss_does_not_change_job_completion(self):
        log = io.StringIO()
        class DisconnectAtCompletion:
            def write(self, text):
                if '"event": "controller_idle"' in text:
                    raise BrokenPipeError('SSH disconnected at completion')
            def flush(self):
                pass
        event = RunLog(log, DisconnectAtCompletion())
        commands = []
        def command(op, *args):
            commands.append(op)
            return (0,0,0,32)
        stream([bytes(3072)]*4, command, len, event, sleep=lambda _:None)
        event('stop_disable_commands_attempted', controller_completion_seen=True)
        events = [json.loads(line) for line in log.getvalue().splitlines()]
        self.assertEqual(commands.count(5), 1)
        self.assertEqual(commands[-3:], [31,2,33])
        self.assertEqual(events[-2]['errors'], [])
        self.assertEqual(events[-2]['event'], 'cleanup')
        self.assertTrue(events[-1]['controller_completion_seen'])
        self.assertNotIn('error', [e['event'] for e in events])

    def test_file_failure_is_not_swallowed(self):
        event = RunLog(BrokenConsole(), io.StringIO())
        with self.assertRaises(BrokenPipeError):
            event('controller_idle')

    def test_actual_closed_stdout_exits_successfully(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'events.jsonl'
            code = '''import sys
from meerk40t.balormk.runlog import RunLog
with open(sys.argv[1], 'w') as f:
    log = RunLog(f)
    for i in range(100):
        log('progress', index=i)
    log('controller_idle')
    log('cleanup', errors=[])
'''
            child = subprocess.Popen([sys.executable, '-c', code, str(path)],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            child.stdout.close()
            self.assertEqual(child.wait(timeout=15), 0, child.stderr.read().decode())
            child.stderr.close()
            events = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(events),102)
            self.assertEqual(events[-1]['event'],'cleanup')
