"""Authoritative on-disk run events with an optional console mirror."""
import datetime
import json
import os
import sys


class RunLog:
    def __init__(self, file, console=None):
        self.file = file
        self.console = sys.stdout if console is None else console

    def __call__(self, name, **data):
        row = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'event': name, **data}
        line = json.dumps(row) + '\n'
        # Disk logging failures must still propagate. Only the optional mirror
        # is best-effort; losing it says nothing about controller completion.
        self.file.write(line)
        self.file.flush()
        if self.console is None:
            return
        try:
            self.console.write(line)
            self.console.flush()
        except (OSError, ValueError):
            if self.console is sys.stdout:
                # Prevent Python's final buffered stdout flush from turning a
                # successful run into exit status 120 after an SSH pipe closes.
                try:
                    with open(os.devnull, 'w') as sink:
                        os.dup2(sink.fileno(), self.console.fileno())
                except (OSError, ValueError, AttributeError):
                    pass
            self.console = None
