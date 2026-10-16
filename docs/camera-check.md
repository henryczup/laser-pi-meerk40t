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
