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
- General live output and red-light framing remain blocked. The bounded square
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
