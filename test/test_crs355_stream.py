import unittest
from meerk40t.balormk.crs355_stream import packets, stream, END


class TestStream(unittest.TestCase):
    def test_packets_preserve_all_commands(self):
        import struct
        commands=[(0x8001,i,i,0,0,0) for i in range(1000)]+[END]
        result=packets(commands)
        decoded=list(struct.iter_unpack('<6H',b''.join(result)))
        self.assertEqual(decoded[:len(commands)],commands)
        self.assertTrue(all(c==END for c in decoded[len(commands):]))

    def test_executes_once_after_three_packets(self):
        events=[]; commands=[]; writes=[]
        def command(op,*args):
            commands.append((op,len(writes)))
            return (0,0,0,32)
        stream([bytes(3072)]*57,command,lambda b:writes.append(b) or len(b),
               lambda *a,**kw:events.append(a[0]),sleep=lambda _:None)
        self.assertEqual([n for op,n in commands if op==5],[3])
        self.assertEqual(len(writes),57)
        self.assertEqual([op for op,n in commands[-3:]],[31,2,33])

    def test_ambiguous_execute_not_retried_and_cleanup_runs(self):
        commands=[]
        def command(op,*args):
            commands.append(op)
            if op==5:
                raise IOError('reply lost')
            return (0,0,0,32)
        with self.assertRaises(IOError):
            stream([bytes(3072)]*4,command,len,lambda *a,**kw:None)
        self.assertEqual(commands.count(5),1)
        self.assertEqual(commands[-3:],[31,2,33])

    def test_deadline_cleans_up(self):
        now=[0]; commands=[]
        def command(op,*args):
            commands.append(op)
            return (0,0,0,0)
        def sleep(dt):
            now[0]+=dt
        with self.assertRaises(TimeoutError):
            stream([bytes(3072)],command,len,lambda *a,**kw:None,
                   timeout=.02,clock=lambda:now[0],sleep=sleep)
        self.assertNotIn(5,commands)
        self.assertEqual(commands[-3:],[31,2,33])
