"""Optional Pi-side completion email; no hardware access and no automatic retries."""
import json
import smtplib
import ssl
import threading
from email.message import EmailMessage
from pathlib import Path


def send(config, event):
    """Use implicit TLS and a private password file, never browser credentials."""
    password = Path(config['password_file']).read_text(encoding='utf-8').strip()
    if not password:
        raise ValueError('Empty SMTP password')
    message = EmailMessage()
    message['From'] = config['sender']
    message['To'] = config['recipient']
    message['Subject'] = 'Laser Pi: job completed'
    message.set_content(
        'The controller reported successful completion of your prepared laser job.\n\n'
        f"Job: {event['label']}\nRun: {event['run_id']}\n\n"
        'Inspect the workpiece before further processing. Controller completion '
        'does not verify the optical result.\n')
    with smtplib.SMTP_SSL(config['host'], config.get('port', 465),
                          timeout=20, context=ssl.create_default_context()) as smtp:
        smtp.login(config['username'], password)
        refused = smtp.send_message(message)
        if refused:
            raise RuntimeError('Recipient refused')


def deliver(config, event, record, sender=send):
    # The claim precedes SMTP: an uncertain delivery is never resent automatically.
    result = dict(event, status='sending')
    try:
        with record.open('x', encoding='utf-8') as stream:
            json.dump(result, stream)
    except FileExistsError:
        return
    try:
        sender(config, event)
        result['status'] = 'accepted_by_smtp'
    except Exception as error:
        result['status'] = 'failed_or_delivery_unknown'
        result['error_type'] = type(error).__name__  # No secrets/server response.
    temp = record.with_suffix('.tmp')
    temp.write_text(json.dumps(result), encoding='utf-8')
    temp.replace(record)


def queue(config, log_path, label):
    if not config or not config.get('enabled'):
        return
    directory = Path(log_path).parent
    event = dict(label=label, run_id=directory.name)
    threading.Thread(target=deliver, args=(dict(config), event,
                     directory / 'completion-email.json'), daemon=True).start()


def watch(station, stop):
    """Reap completed processes even when every browser is closed."""
    while not stop.wait(1):
        try:
            with station.guard:
                station.status()
        except Exception:
            # Never restart, resume, or retry a laser process on observer failure.
            continue


def configure():
    """Run interactively on the Pi; never supply a password on the command line."""
    import argparse
    import getpass
    import os
    parser = argparse.ArgumentParser(description=configure.__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--sender', required=True)
    parser.add_argument('--recipient', required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    password = getpass.getpass('Gmail app password (hidden): ').replace(' ', '')
    if len(password) != 16 or not password.isascii() or not password.isalpha():
        raise ValueError('Expected a 16-letter Gmail app password; configuration unchanged')
    path = args.config.with_name('smtp-app-password')
    # A fresh file avoids silently replacing credentials already used elsewhere.
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(password)
    config['completion_email'] = dict(enabled=True, host='smtp.gmail.com', port=465,
        username=args.sender, sender=args.sender, recipient=args.recipient,
        password_file=str(path.resolve()))
    temp = args.config.with_name(args.config.name + '.email-setup.tmp')
    fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(config, stream, indent=2)
    temp.replace(args.config)
    print('Email configured. Restart the web service only when idle to activate it.')


if __name__ == '__main__':
    configure()
