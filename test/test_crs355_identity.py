import unittest
from unittest.mock import Mock
from meerk40t.balormk.crs355_identity import identify


class TestIdentitySync(unittest.TestCase):
    def setUp(self):
        self.expected = dict(version={'words': [0, 100, 2, 32]}, serial={'words': [0, 3, 4, 32]})
        self.replies = [(0,100,2,32),(0,3,4,32)] * 2

    def test_stale_reply_is_drained_then_identity_checked_twice(self):
        dev = Mock()
        dev.read.side_effect = [b'12345678', TimeoutError()]
        send = Mock(side_effect=self.replies)
        version, serial, drained = identify(dev, send, self.expected, TimeoutError)
        self.assertEqual(drained, 1)
        self.assertEqual([c.args[0] for c in send.call_args_list], [7,9,7,9])
        dev.write.assert_not_called()

    def test_queue_flood_or_io_error_never_sends_commands(self):
        for effect in ([b'12345678']*8, OSError('disconnected'), [b'short']):
            dev, send = Mock(), Mock()
            dev.read.side_effect = effect
            with self.assertRaises((RuntimeError, OSError)):
                identify(dev, send, self.expected, TimeoutError)
            send.assert_not_called()

    def test_mismatch_and_busy_do_not_retry(self):
        for replies in ([(0,999,2,32),(0,3,4,32)], [(0,100,2,36),(0,3,4,36)]):
            dev = Mock()
            dev.read.side_effect = TimeoutError()
            send = Mock(side_effect=replies)
            with self.assertRaises(RuntimeError):
                identify(dev, send, self.expected, TimeoutError)
            self.assertEqual(send.call_count, 2)

    def test_second_sample_must_also_match(self):
        dev = Mock()
        dev.read.side_effect = TimeoutError()
        send = Mock(side_effect=self.replies[:2]+[(0,999,2,32),(0,3,4,32)])
        with self.assertRaises(RuntimeError):
            identify(dev, send, self.expected, TimeoutError)
