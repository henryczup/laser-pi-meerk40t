# Fork development

Read docs/crs355-pi.md before changing CRS source control.
Keep the CRS profile simulation-only. Do not fire, connect to USB, restart the
active station or deploy as part of offline tests. Never retry ambiguous jobs.
Preserve source-specific initialization, correction and cleanup, along with
external controller identity, completed-run markers and logs.
Do not commit private machine configuration, correction files, credentials,
camera captures or controller identities to this public fork.
Validate against upstream 0.9.9100 and the private station regression fixtures.
