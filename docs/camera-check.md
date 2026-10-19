# Check the Pi camera

Run this workflow when asked to inspect the camera or work area. It only fetches
the existing localhost camera service through SSH; it does not start services,
deploy code, contact the laser controller, frame, or engrave.

From this checkout, using a Python environment with Pillow:

```text
python -m meerk40t.camera.check_pi --host <Pi-address> --user <Pi-user> --key <private-key-path> --known-hosts <known-hosts-file> --output-dir <private-capture-directory>
```

Use `--host-key-alias <previously-verified-host>` when the same Pi has moved to a
new address and its verified SSH key is recorded under that alias. Never disable
host key verification. Keep addresses and credentials in private local records.

The Pi must already be running the Picamera2 preview service on localhost:8080.
Each request calls `/snapshot.jpg`, which captures a new frame. SSH is limited to
one connection attempt and a 25-second overall timeout. No browser tunnel is needed.
The command validates JPEG decoding and writes a uniquely named image and JSON
record outside the repository, including receipt time, dimensions, and SHA256.
Failure produces a JSON error record and exit code 1, never an old image.

## Proactive checks before physical-state replies

When the operator changes the board or flips it, or asks about placement,
alignment, or cutting results, capture and inspect a fresh image before the
substantive reply. Standing permission covers these checks; do not ask again.
Report what is visible and any obstruction or uncertainty. A blank painted face
cannot independently identify top versus bottom; use the operator's statement
for face identity. On capture failure, state that the live view is unavailable.
Code, documentation, and UI-only replies do not require a camera check.

## Agent inspection procedure

1. Run the command with the station's verified SSH identity and current address.
2. If it succeeds, open the returned absolute image path with the image-view tool.
3. Report what is actually visible: whether the bed/material is in view, focus,
   lighting, obstructions, and apparent material position. Link the saved image.
4. If it fails, report the error and connectivity limitation. Do not present a
   previous capture as live, restart services, or initiate laser activity.

A capture is a single observation. It does not establish calibrated dimensions,
UV emission state, optical power, safe operation, or permission to run a job.
Camera calibration and measurements require separate validation.

Offline checks: `python -m unittest test.test_camera_check_pi`.

For iterative red-frame positioning, follow [camera-frame-alignment.md](camera-frame-alignment.md).

## Exposure for red framing

The preview reads camera-controls.json beside its executable on snapshot requests.
It applies validated Picamera2 controls only when that file changes. Replace the
JSON atomically. GET /metadata reports actual exposure and gain. These controls
change the camera only. Keep the file and sweep captures in private station data.

Compare exposure compensation first, then manual exposure with low analogue gain
if short exposures fragment the moving outline. The October 16 sweep compared
EV 0/-1/-2/-3 and 60/80/100 ms at gain 1. The selected framing view uses
AeEnable=false, ExposureTime=100000 microseconds, AnalogueGain=1.0: darker than
the initial auto view while retaining more of the moving outline. Reassess when
lighting changes; this is a viewing preset, not camera or laser calibration.
To restore automatic exposure, set AeEnable=true and ExposureValue=0.
