# Email when a job finishes

The optional Pi-side completion observer runs even with no browser open and the
laptop asleep. It only observes web-service-owned processes; jobs launched by
other scripts are not monitored. It never starts or retries a laser operation.

An alert requires a cut process to exit successfully with the existing controller
completion evidence and no cleanup-error event. Framing, cancellation and failed
jobs do not generate success alerts. The email identifies the job and run and
asks the operator to inspect the result; it does not claim optical verification.

## Gmail setup

Use an app password, not your normal Google password. Google requires 2-Step
Verification and may not offer app passwords on some accounts. See
[Google's app-password instructions](https://support.google.com/mail/answer/185833).

The account owner should create a dedicated app password and enter it in a private
interactive Pi terminal. Do not paste it into chat, a command argument, or Git.
With the standalone module beside the deployed web service, run:

```sh
python3 /path/to/frame-controls/completion_email.py \
  --config /path/to/private/frame-web-config.json \
  --sender you@gmail.com --recipient you@gmail.com
```

The hidden prompt stores it in `smtp-app-password` beside the configuration, with
owner-only permissions. The helper configures Gmail SMTP over verified implicit
TLS on port 465. It refuses to overwrite an existing password file. Keep the
whole private configuration directory out of Git.

Check that the station is idle before activating the new configuration with a
web-service restart. Sending a test email must not involve a test engraving.
The phone's mail app must have notifications enabled; SMTP acceptance cannot
guarantee inbox delivery or a phone notification.

## Records and failure behavior

Each completed run gets `completion-email.json` in its private run directory.
The worker claims this file exclusively before contacting SMTP. Status is
`sending`, `accepted_by_smtp`, or `failed_or_delivery_unknown`. Only exception
types are recorded, not passwords or SMTP response bodies. SMTP has a bounded
timeout and runs outside the station control lock.

There are no automatic delivery retries: a timeout may have occurred after the
provider accepted the message. A crash during sending can leave `sending`.
Inspect delivery records before manually sending anything again. Email failure
does not change the laser's completion state or resubmit its job.

This version does not replay old completions after service restart, and cannot
recover notification monitoring of a process lost with that restart. Keep the
web service running for the full job. Alerts are disabled unless the private
`completion_email.enabled` setting is true. Credentials stay on the Pi.

Offline verification: `python -m unittest test.test_completion_email` uses mock
SMTP and fake completion records; it sends no email and accesses no laser USB.
