"""Explicit bounded passes with a cooperative pause between verified layers.

No USB commands here: the reviewed child runner owns all controller operations.
"""
import argparse
import json
import signal
import subprocess
import sys
import time
from pathlib import Path


def completed(path):
    events = [json.loads(line) for line in Path(path).read_text().splitlines()]
    return (any(e.get('event') == 'cleanup' and e.get('errors') == [] for e in events)
            and any(e.get('event') == 'stop_disable_commands_attempted'
                    and e.get('controller_completion_seen') is True for e in events)
            and not any(e.get('event') in ('error', 'cleanup_error') or
                        (e.get('event') == 'cleanup' and e.get('errors')) for e in events))


def write_state(directory, **state):
    path = directory / 'state.json'
    temp = directory / 'state.tmp'
    temp.write_text(json.dumps(state))
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child-runner', required=True)
    parser.add_argument('--passes', type=int, choices=range(1, 21), required=True)
    parser.add_argument('--control-dir', type=Path, required=True)
    options, args = parser.parse_known_args()
    command = [sys.executable, '-u', options.child_runner]
    if '--execute-approved-fill' not in args:
        return subprocess.run(command + args).returncode
    index = args.index('--run-id')
    root = args[index + 1]
    data = Path(args[args.index('--data-dir') + 1])
    directory = options.control_dir
    directory.mkdir(exist_ok=False, parents=True)
    (directory / 'request.json').write_text(json.dumps(dict(run_id=root, passes=options.passes)))
    child = None
    stopping = False

    def stop(sig, frame):
        nonlocal stopping
        stopping = True
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGINT)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    count = 0
    try:
        for number in range(1, options.passes + 1):
            while (directory / 'pause').exists() and not stopping:
                write_state(directory, phase='paused', completed=count, total=options.passes)
                time.sleep(.2)
            if stopping:
                raise RuntimeError('Stopped; remaining layers cancelled')
            current = list(args)
            current[index + 1] = root + '-p' + str(number)
            write_state(directory, phase='running', completed=count, total=options.passes, layer=number)
            print(f'START additional pass {number}/{options.passes}', flush=True)
            child = subprocess.Popen(command + current)
            result = child.wait()
            if result or stopping or not completed(data / ('fill-' + current[index + 1] + '.jsonl')):
                raise RuntimeError('Layer interrupted or completion unverified; no repeat')
            count = number
            print(f'COMPLETED additional pass {number}/{options.passes}', flush=True)
        write_state(directory, phase='complete', completed=count, total=options.passes)
        print(f'BATCH COMPLETE: exactly {count} additional passes', flush=True)
        return 0
    except BaseException:
        write_state(directory, phase='stopped' if stopping else 'failed', completed=count, total=options.passes)
        raise


if __name__ == '__main__':
    raise SystemExit(main())
