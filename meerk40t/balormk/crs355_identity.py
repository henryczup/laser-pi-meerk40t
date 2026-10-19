"""Bounded preflight synchronization, before any source initialization.

Caller must hold the exclusive station hardware lock. Never use during streaming
or retry an execution after failure. Only queued input replies are discarded.
"""


def identify(device, send, expected, timeout_error):
    drained = 0
    for _ in range(8):
        try:
            reply = bytes(device.read(0x88, 8, timeout=100))
        except timeout_error:
            break
        if len(reply) != 8:
            raise RuntimeError('Malformed queued USB reply')
        drained += 1
    else:
        raise RuntimeError('USB reply queue did not empty; refusing initialization')
    observed = []
    for _ in range(2):
        version, serial = send(7), send(9)
        if list(version[:3]) != expected['version']['words'][:3]:
            raise RuntimeError('Controller version mismatch after USB synchronization')
        if list(serial[:3]) != expected['serial']['words'][:3]:
            raise RuntimeError('Controller serial mismatch after USB synchronization')
        if version[3] & 4 or serial[3] & 4:
            raise RuntimeError('Controller busy; refusing initialization')
        observed.append((version, serial))
    return observed[-1][0], observed[-1][1], drained
