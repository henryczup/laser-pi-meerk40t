# Independent local development

The active checkout is `C:/Users/henry/dev/laser-pi-meerk40t`. Create its own virtual
environment rather than borrowing an interpreter from the retired setup repo:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e . numpy==2.0.2 pillow==11.3.0 pyserial==3.5 pyusb==1.3.1
.venv/Scripts/python.exe -m unittest test.test_crs355 test.test_web_job_controls test.test_frame_web test.test_batch_progress test.test_camera_alignment test.test_camera_check_pi test.test_crs355_identity test.test_crs355_frame -q
```

This is the minimal station development environment; optional desktop, DXF and
Raspberry Pi camera dependencies are separate. Python 3.9.13 and MeerK40t
0.9.9100 were used for the October 18, 2026 migration checks.

Historical calibration fixtures and run records remain outside Git. Run
`python -m test.verify_crs355_capture --data-dir <private-reference-directory>`
for offline protocol equivalence checks. Never invoke historical live runners
as installation tests. Retiring the laptop setup does not alter Pi services.
