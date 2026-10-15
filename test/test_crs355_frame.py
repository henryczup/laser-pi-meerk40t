import struct
import unittest
from meerk40t.balormk.crs355_frame import packet, rectangle, trace


class TestFrame(unittest.TestCase):
    def test_outline_is_bounded(self):
        from meerk40t.balormk.crs355_frame import outline_points
        self.assertTrue(outline_points([[[50,50],[100,100],[50,50]]], [49.5,40,101,120],1,1))
        for paths in ([[[0,0],[100,100]]], [[[50,50],[float('nan'),60]]], []):
            with self.assertRaises(ValueError):
                outline_points(paths,[49.5,40,101,120],1,1)

    def test_forbids_every_unlisted_opcode(self):
        from meerk40t.balormk.crs355_frame import ALLOWED
        for op in range(65536):
            if op not in ALLOWED:
                with self.assertRaises(ValueError):
                    packet(op)
        for op in (4,5,15,33,0x8003,0x8005,0x8011,0x8051):
            with self.assertRaises(ValueError):
                packet(op,0)

    def test_rectangle_bounds(self):
        points=rectangle(49.5,40,101,120,1,1)
        self.assertEqual(len(points),222)
        for rect in ((0,0,202,120),(0,0,-1,10),(float('nan'),0,1,1)):
            with self.assertRaises(ValueError):
                rectangle(*rect,1,1)

    def test_trace_is_bounded_and_no_emission_commands(self):
        now=[0.0]; sent=[]
        def send(op,*args):
            sent.append(struct.unpack('<6H',packet(op,*args)))
        def sleep(seconds):
            now[0]+=seconds
        trace(send,[(32000,32000),(33000,33000)],.02,lambda:now[0],sleep)
        self.assertGreaterEqual(now[0],.02)
        self.assertEqual([p[0] for p in sent[-3:]],[31,2,14])
        self.assertTrue(set(p[0] for p in sent) <= {31,2,14,18,13})

    def test_failure_still_disables(self):
        sent=[]
        def send(op,*args):
            sent.append(op)
            if op==13:
                raise IOError('Disconnected')
        with self.assertRaises(IOError):
            trace(send,[(32768,32768)],1)
        self.assertEqual(sent[-3:],[31,2,14])


if __name__=='__main__':
    unittest.main()
