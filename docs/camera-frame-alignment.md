# Repeatable camera-assisted frame alignment

For operator nudge controls beside the live preview, see [frame-web.md](frame-web.md).

This is an agent-operated visual alignment loop for the existing bounded red
framer. It prepares placement candidates, not cutting jobs. It is not automatic
camera calibration or a precision registration algorithm.

## Establish the session

Read `docs/crs355-pi.md` and `docs/camera-check.md`. Identify the correct face,
section, original outline and original field rectangle. Check previous job logs
for completion and cleanup, and confirm no job is running. Preserve all records.
The operator has granted standing permission for camera checks and bounded red-only
framing for alignment and sizing, including camera-guided placement adjustments
and saving the resulting placement. Do not ask for frame-placement approval or
permission to repeat camera checks or bounded frames. Report the observed result
and limitations directly. This replaces the earlier session-specific request to
approve the frame. Do not require a verbal "UV disabled; red pointer
on" confirmation or a repeated checkbox before framing. Use the reviewed red-only
runner and preserve its identity checks, command restrictions and output cleanup.
Camera images establish placement, not UV emission state; do not report the source
as disabled based on an image. Investigate concrete evidence of unintended marking
or a controller fault before continuing. Framing permission does not authorize engraving.

Keep the board and camera stationary while adjusting software placement. Request
that the operator stop moving them if images show motion. Capture a fresh image
with `meerk40t.camera.check_pi`, then inspect it using the image-view tool.
Do not infer source readiness from visible spots.

## Iterate: capture, prepare, frame, compare

1. Identify a reliable existing section boundary or registration marks. A taper
   endpoint may end before the section boundary; do not substitute it for the seam.
   Inspect at least two separated locations along the joining edge where available.
2. Prepare a translation from the immutable original outline. Use a new private
   directory for every trial; never accumulate rounded shifts from the last file:

   ```text
   python -m meerk40t.camera.prepare_alignment --original-outline <original.json> --original-rect X Y W H --shift DX DY --before-image <fresh.jpg> --output-dir <private-new-trial-directory>
   ```

   `DX DY` is the total design-coordinate shift, not screen pixels. The helper
   validates finite coordinates and field bounds, preserves size and shape, and
   records hashes of the original, candidate, and before image. It cannot frame,
   connect to the Pi, or approve a cut.
3. Transfer only the candidate outline to a unique private path on the Pi using
   the station's verified SSH identity. First run the existing framer WITHOUT
   `--execute-red-frame`, using the candidate's `frame_rect_mm` and outline path.
   Verify validation succeeds. Do not deploy or change source/calibration.
4. Run the validated command with `--execute-red-frame --fast --seconds 30`.
   The existing runner checks controller identity, correction, busy state and
   exclusive lock. Do not run simultaneous frame processes. Do not auto-retry
   after ambiguous USB or connection failure; first establish stopped state.
5. While it is tracing, use `check_pi` to capture a new uniquely named image and
   inspect it. A short camera exposure may show only fragments; another snapshot
   during the SAME frame is fine. Save the capture manifest and image path with
   this trial. A webpage is for operator viewing, not evidence of freshness.
6. Compare the projected joining edge with the existing boundary. Estimate a
   conservative translation from the known projected rectangle and observed
   movement between trials. This is only a visual estimate. Make a smaller
   correction as the residual shrinks. If alignment worsens, revisit the mapping;
   do not keep moving blindly or rescale the antenna to force a fit.
7. Wait for `RED FRAME STOPPED` and successful cleanup before the next trial.
   Stop after at most three trials per batch, or sooner if the edge appears aligned,
   evidence is unclear, board/camera moves, rotation is needed, field limits are
   reached, or a transport/cleanup error occurs. Report the limitation explicitly.

## Save the result

Keep `candidate.json` unchanged. Add a separate `assessment.json` in the trial
directory containing the after-image and its manifest, observed residual at each
reference location (pixels or qualitative, not invented millimeters), frame
completion/cleanup result, and status `visual_alignment_candidate` or `unresolved`.
State camera calibration and red-to-UV registration limitations. Never mark
`cut_approved` true solely because of camera appearance.

Report the total shift, what matched, what remains uncertain, and whether framing
stopped. No separate operator approval of frame placement is required. Any
subsequent cutting job must explicitly use the saved, inspected placement
transform, retain the original pattern scale, pass offline validation and receive
the applicable marking authorization/readiness. Do not silently reuse the old
unshifted cut or treat a saved frame candidate as permission to fire.

The last session's shift is specific to that board placement. Never reuse it after
moving the board, changing faces, changing the lens, or moving the camera without
fresh inspection. Keep all station-specific values and images outside Git.

## Operator preview

Use a local-only SSH tunnel to the Pi camera service, with the station's verified
host key and key file:

```text
ssh -N -T -o BatchMode=yes -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -L 127.0.0.1:8084:127.0.0.1:8080 <Pi-user>@<Pi-host>
```

Supply the private station key/known-hosts options as documented locally. On
Windows launch background helpers hidden. Verify HTTP 200 and a fresh snapshot
before linking `http://127.0.0.1:8084/`. If the tunnel is unavailable, report that
instead of calling the page live. Never expose the service publicly for this flow.

Offline checks:
`python -m unittest test.test_camera_check_pi test.test_camera_alignment test.test_crs355_frame`
