# Fork development

Read docs/crs355-pi.md before changing CRS source control.
Keep the CRS profile simulation-only. Do not fire, connect to USB, restart the
active station or deploy as part of offline tests. Never retry ambiguous jobs.
Preserve source-specific initialization, correction and cleanup, along with
external controller identity, completed-run markers and logs.
Do not commit private machine configuration, correction files, credentials,
camera captures or controller identities to this public fork.
Validate against upstream 0.9.9100 and the private station regression fixtures.

For camera inspection, follow docs/camera-check.md. Fetch a fresh snapshot with
meerk40t.camera.check_pi and inspect the returned image; never treat a cached
preview as current. Keep captures outside the public repository.

For camera-assisted positioning, follow docs/camera-frame-alignment.md. Use
meerk40t.camera.prepare_alignment for offline translation candidates from the
immutable original. Inspect fresh images between bounded red frames, preserve
each trial, and never promote visual alignment into automatic cut authorization.

For each new design prepared for this station, publish its framing outline and
settings to the private web design catalog using docs/frame-web.md. The web app
must show the current design, not a hard-coded prior job. Settings requests must
be rebuilt and validated before enabling their cutting job; never silently run
old toolpaths after a parameter edit. Preserve unrelated catalog entries and logs.
