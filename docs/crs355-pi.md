# CRS-355-5 Raspberry Pi fork

This fork starts at upstream **0.9.9100**, commit
`2ccd5e0b2efbb2355bb91dc096f1a940491f77e9`.
Development branch: `codex/crs355-pi-support`.
The previous private setup repository is retained as `laser-pi-meerk40t-legacy`.

## Source changes

- Opt-in `crs355_profile` chooses `CRS355Controller` directly in the Balor driver;
  no runtime monkey-patching or replacement of other device controllers.
- Captured source initialization, UV duty/frequency commands, travel/mark speed
  conversion, jump delays and coordinate rounding are retained.
- Explicit external correction-file SHA256 and separate X/Y scales are required.
  The profile checks the 200 mm field, UV source and simulation mode.
- Mock responses are deterministic only for this profile.
- General live output and integrated GUI framing remain blocked. The bounded square
  runner is separate and retains identity checks, fixed artwork/calibration
  hashes, a deadline, exclusive run records and stop/disable cleanup.
- `python -m meerk40t.camera.pi_preview` runs the CSI preview on localhost:8080.
  It requires system Picamera2 on Raspberry Pi OS, opens no camera on import,
  and is separate from MeerK40t's OpenCV camera panel. Use SSH forwarding.

The captured recipe is 500 mm/s mark, 4000 mm/s travel, 120 kHz, UV duty 12%
(internal power 120). This matches the captured Q=1 command; it does not establish
measured optical watts or pulse duration. It is not a validated PCB paint recipe.

## Private machine data

Keep calibration, configuration, controller identity, jobs, completed-run markers,
logs and credentials outside this public repository. Existing `~/laser-agent`
data must be preserved during migration. Removing an old code installation must
never remove these records or reset a completed run.

Device settings in a **separate candidate configuration**:

```ini
crs355_profile = True
source = uv
mock = True
lens_size = 200mm
crs355_scale_x = <existing validated X scale>
crs355_scale_y = <existing validated Y scale>
crs355_cor_sha256 = <existing correction SHA256>
corfile = <absolute external correction path>
```

## Offline verification

```sh
python -m unittest test.test_crs355 -v
python -m test.verify_crs355_capture --data-dir /path/to/existing/reference
python -m meerk40t.balormk.crs355_square_test --data-dir /path/to/existing/reference
```

The capture verifier requires the private historical fixtures and adapter only
to obtain the original calibration scales; it does not run that adapter's
launcher. None of these commands access laser USB or fire.

For an explicitly authorized single physical check, the square runner accepts
`--execute-approved-single-test --run-id UNIQUE_NAME`. Do not invoke this in CI
or as an installation check. Never automatically retry after an uncertain result.

## Migration gates

1. Keep the active Pi environment and camera service unchanged. Stage this fork
   in a separate checkout and virtual environment with system packages available.
2. Pass the source tests and private capture checks on the Pi.
3. Prepare a fresh bounded test record, obtain current physical readiness, run
   once and inspect the actual mark. Controller completion is not optical proof.
   Recent Pi 4 attempts were not confirmed to produce visible marks; resolve
   that before declaring the fork ready to replace the station.
4. Test camera preview after an intentional, temporary handover of the camera.
5. Back up configuration/data and old environment. Switch entry points and camera
   service to the fork only after acceptance; retain a documented rollback.
6. Retire the old adapter/code after successful operation. Preserve private data
   and historical logs; retain the legacy repository as the development record.

No physical test, active service switch or removal is performed merely by
installing or testing this fork.

## Bounded external-pointer framing

`python -m meerk40t.balormk.crs355_frame --data-dir /path/to/reference`
validates the rectangle and correction offline. The default rectangle is
101 x 120 mm at (49.5, 40) in a 200 mm field, for Vivaldi section alignment.
`--execute-red-frame --seconds 60` explicitly runs scanner-only positioning
for at most 60 seconds, plus bounded USB command latency. Keep UV emission
physically disabled and enable the independent red pointer beforehand.

The command allowlist excludes EnableLaser, LaserSignalOn, GPIO writes,
ExecuteList and every list/mark opcode. It uses direct GotoXY moves after
DisableLaser/LaserSignalOff and correction upload, with identity checks and
an exclusive framing lock. Stop/disable/signal-off cleanup runs on trace exit
or error. It does not alter the active station service or general live guard.
No retries follow a transport failure. A physically controlled red pointer may
remain lit and stationary afterward; use its normal switch to turn it off.

This is a moving boundary trace, not an optically calibrated rectangle yet.
The saved red-dot scale differs from the marking transform; this diagnostic
uses marking coordinates and does not guess how to apply that optical offset.
Measure the projected bounds and verify red/UV alignment before fabrication.
Do not align a full 202 mm board as though this were its full outline.

`python -m unittest test.test_crs355_frame -v` tests the opcode allowlist,
geometry bounds, duration limit and error cleanup without accessing hardware.

## Reviewed fill jobs

`crs355_fill` accepts external command text with an explicit SHA256, enforcing
the captured source prefix and independent jump/mark stroke sequence. By default
it only validates. Execution requires `--execute-approved-fill` and a unique
`--run-id`, uses the existing identity and correction, and preserves exclusive
run records. It shares the framing lock. General application live output is
still blocked.

`crs355_stream` splits into 256-command packets and follows upstream's three
packet prefill before a single ExecuteList. Tests cover packet preservation,
single execution, ambiguous errors without retries, timeout and cleanup.
This streaming path passed offline tests on Windows and Pi; physical acceptance
is still pending. Keep UV disabled until the operator explicitly confirms current
marking readiness. The selected PCB coating recipe has not been verified by a
paint-clearance trial.

## Verification recorded October 15, 2026

Source commit `a1dba7d71` passed 11 CRS/stock-galvo tests on Windows and
Raspberry Pi 4. Private capture comparison passed all 4225 correction entries,
18 grid endpoints, initialization and eight source/timing command words.
The bounded square runner passed offline validation on both systems.

The Pi candidate is `/home/henry/meerk40t-candidates/a1dba7d71`, installed in
`/home/henry/.venvs/meerk40t-fork-candidate`. Test log:
`/home/henry/meerk40t-fork-tests.log`. Active environment remains
`/home/henry/.venvs/meerk40t`; the active camera service still uses the old
preview script. No physical job was run during fork development.
