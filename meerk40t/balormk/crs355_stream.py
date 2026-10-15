"""Packetization for reviewed CRS hatch jobs; no hardware access on import."""
import struct
import time

END = (0x8002,0,0,0,0,0)


def packets(commands):
    if not commands or tuple(commands[-1]) != END:
        raise ValueError('Missing end of job')
    result=[]
    for start in range(0,len(commands),256):
        block=list(commands[start:start+256])
        block += [END]*(256-len(block))
        result.append(b''.join(struct.pack('<6H',*c) for c in block))
    return result


def stream(blocks, command, write, event, timeout=1800,
           clock=time.monotonic, sleep=time.sleep):
    """Follow upstream's three-packet prefill, with one ExecuteList and no retry.

    Caller owns identity, job/calibration checks, exclusive records and source
    initialization. This function always attempts stop/disable/port-zero cleanup.
    """
    deadline=clock()+timeout
    started=False
    def wait(idle=False):
        while clock()<deadline:
            status=command(7)[3]
            if status&32 and (not idle or not status&4):
                return
            sleep(.01)
        raise TimeoutError('Bounded job deadline exceeded')
    try:
        for index,block in enumerate(blocks):
            if len(block)!=3072:
                raise ValueError('Invalid packet size')
            wait()
            if write(block)!=3072:
                raise IOError('Short packet write; not retried')
            command(0x19,0)
            event('packet_sent',index=index+1,total=len(blocks))
            if not started and (index==2 or index==len(blocks)-1):
                # Mark attempted BEFORE sending; never repeat on error.
                started=True
                event('execute_attempted')
                command(5)
                command(0x16,1)
                command(0x1d,2000,20,1)
                command(0x21,0)
        sleep(.3)
        wait(idle=True)
        event('controller_idle',physical_result_unverified=True)
    finally:
        failures=[]
        for op,args in [(0x1f,()),(2,()),(0x21,(0,))]:
            try:
                command(op,*args)
            except Exception as exc:
                failures.append(repr(exc))
        event('cleanup',errors=failures)
        if failures:
            raise RuntimeError('Cleanup failed: '+str(failures))
