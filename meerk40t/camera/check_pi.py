"""Fetch a fresh CSI snapshot over SSH without accessing laser controls."""
import argparse
import hashlib
import io
import json
import shlex
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

MAX_BYTES = 12 * 1024 * 1024


def ssh_command(host, user, key, known_hosts, host_key_alias=None):
    # SSH interprets destinations beginning with '-' as options.
    for value in (host, user):
        if not value or value.startswith('-') or any(c.isspace() for c in value):
            raise ValueError('Invalid SSH host or user')
    remote = (
        'import sys, urllib.request; '
        'r=urllib.request.urlopen("http://127.0.0.1:8080/snapshot.jpg", timeout=12); '
        'sys.stdout.buffer.write(r.read(%d))' % (MAX_BYTES + 1)
    )
    command = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
               '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectionAttempts=1',
               '-o', 'UserKnownHostsFile=' + str(known_hosts), '-i', str(key)]
    if host_key_alias:
        command += ['-o', 'HostKeyAlias=' + host_key_alias]
    return command + [user + '@' + host, 'python3 -c ' + shlex.quote(remote)]


def validate_jpeg(body):
    from PIL import Image
    if not body or len(body) > MAX_BYTES:
        raise ValueError('Empty or oversized camera response')
    with Image.open(io.BytesIO(body)) as picture:
        if picture.format != 'JPEG':
            raise ValueError('Camera response is not JPEG')
        width, height = picture.size
        if width * height > 20000000:
            raise ValueError('Camera image exceeds pixel limit')
        picture.load()
    return width, height


def capture(command, output_dir, host, runner=subprocess.run):
    output_dir = Path(output_dir).resolve()
    repo = Path(__file__).resolve().parents[2]
    if output_dir == repo or repo in output_dir.parents:
        raise ValueError('Save private camera captures outside this repository')
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    base = output_dir / ('camera-' + stamp + '-' + uuid.uuid4().hex[:8])
    record = {'requested_at_utc': stamp, 'host': host, 'status': 'failed'}
    try:
        result = runner(command, capture_output=True, timeout=25, check=False)
        if result.returncode:
            raise RuntimeError('SSH/snapshot failed: ' + result.stderr.decode('utf-8', errors='replace')[-2000:])
        width, height = validate_jpeg(result.stdout)
        path = base.with_suffix('.jpg')
        with path.open('xb') as stream:
            stream.write(result.stdout)
        record.update(status='captured', image=str(path), width=width, height=height,
                      received_at_utc=datetime.now(timezone.utc).isoformat(),
                      sha256=hashlib.sha256(result.stdout).hexdigest())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        record['error'] = str(error)
    manifest = base.with_suffix('.json')
    with manifest.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2)
    return record, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('host', 'user', 'key', 'known-hosts', 'output-dir'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--host-key-alias')
    args = parser.parse_args()
    command = ssh_command(args.host, args.user, args.key, args.known_hosts, args.host_key_alias)
    record, manifest = capture(command, args.output_dir, args.host)
    print(json.dumps(dict(record, manifest=str(manifest)), indent=2))
    return 0 if record['status'] == 'captured' else 1


if __name__ == '__main__':
    raise SystemExit(main())
