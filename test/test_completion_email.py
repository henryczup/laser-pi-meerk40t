import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from meerk40t.camera import completion_email
from meerk40t.camera.frame_web import Station


class CompletionEmailTest(unittest.TestCase):
    def test_durable_claim_prevents_duplicate_and_ambiguous_retry(self):
        with tempfile.TemporaryDirectory() as d:
            record = Path(d) / 'email.json'
            sender = Mock(side_effect=TimeoutError('secret server response'))
            event = dict(label='fixture', run_id='fixture-run')
            completion_email.deliver({}, event, record, sender)
            completion_email.deliver({}, event, record, sender)
            sender.assert_called_once()
            text = record.read_text()
            self.assertNotIn('secret', text)
            self.assertEqual(json.loads(text)['status'], 'failed_or_delivery_unknown')

    def test_smtp_accepted_record(self):
        with tempfile.TemporaryDirectory() as d:
            record = Path(d) / 'email.json'
            completion_email.deliver({}, dict(label='fixture', run_id='fixture'), record, Mock())
            self.assertEqual(json.loads(record.read_text())['status'], 'accepted_by_smtp')

    def test_only_successful_cut_notifies(self):
        for kind, code, log, expected in (
            ('cut', 0, '{"controller_completion_seen": true}', True),
            ('cut', 1, '{"controller_completion_seen": true}', False),
            ('cut', 0, '{"controller_completion_seen": false}', False),
            ('cut', 0, '{"controller_completion_seen": true}\ncleanup_error', False),
            ('frame', 0, 'RED FRAME STOPPED', False),
        ):
            with self.subTest(kind=kind, code=code, log=log), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                outline = root/'outline.json'
                outline.write_text('{"paths": [[[0,0],[1,1]]]}')
                s = Station(dict(outline=str(outline), rect=[0,0,1,1]))
                s.log_path = root/'cut.log'
                s.log_path.write_text(log)
                s.log = Mock()
                s.kind = kind
                s.process = Mock(returncode=code)
                s.process.poll.return_value = code
                with patch.object(completion_email, 'queue') as queue:
                    s.status()
                    s.status()
                    self.assertEqual(queue.call_count, int(expected))

    def test_observer_works_without_browser(self):
        station = Mock(guard=threading.Lock())
        stop = Mock()
        stop.wait.side_effect = [False, True]
        completion_email.watch(station, stop)
        station.status.assert_called_once()

    def test_tls_and_private_password_file(self):
        with tempfile.TemporaryDirectory() as d:
            password = Path(d)/'password'
            password.write_text('private-password')
            cfg = dict(host='smtp.example.com', sender='sender@example.com',
                       recipient='recipient@example.com', username='sender@example.com',
                       password_file=str(password))
            with patch.object(completion_email.smtplib, 'SMTP_SSL') as smtp:
                smtp.return_value.__enter__.return_value.send_message.return_value = {}
                completion_email.send(cfg, dict(label='fixture', run_id='fixture'))
                client = smtp.return_value.__enter__.return_value
                client.login.assert_called_once_with('sender@example.com', 'private-password')
                self.assertNotIn('private-password', str(client.send_message.call_args))
