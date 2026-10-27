# Camera page with frame steering

For the operator workflow and example chat instructions, see
[Using Codex with the live station page](codex-ui-workflow.md).

Optional [completion email](completion-email.md) runs on the Pi without requiring
an open browser. It requires private SMTP setup and is disabled by default.

Operator update (October 18): the SVG drop area was removed at the operator's request.
The upload API remains available for preparation tools. The page has Start cutting,
Pause, Continue beside Frame and Stop. The compact current job summary identifies
what Start will execute. A completed or ambiguous request remains protected by
its durable marker; these controls never erase a marker to repeat a job.

SVG uploads (up to 1 MB) are private preparation requests, not executable jobs.
The server rejects scripts, event handlers, entities, external resources, and
unsupported elements. Convert text to paths before uploading. Files are archived
with a hash and dimensions; an upload invalidates the previous cut and framing
until the agent prepares and selects the new design. Upload is locked during
active operations. Selection of a prepared design clears the pending upload.

Pause means **pause between layers**, not immediate hardware pause. A configured
job opts in with `pause_between_layers: true` and integer `passes` (1–20), and its
`runner` must be the reviewed single-pass fill runner, not an existing batch loop.
The web service wraps it with `layer_batch.py`. Each child keeps independent
identity, correction, completion and cleanup checks. Pause writes a per-run
request; only after the current layer finishes and cleanup is verified does the
batch report Paused. Continue removes that request. Stop cancels the batch, including
while paused. The wrapper never sends pause/resume USB opcodes and never suspends
a process while the controller continues unattended. Unsupported running jobs
show disabled Pause/Continue. A single layer can finish before pause takes effect.
No interrupted run resumes, no completed layer repeats, and no restart auto-runs.

Offline tests: `python -m unittest test.test_web_job_controls test.test_frame_web`.
Use a fake child runner to test pause/continue; deployment is separate and allowed
only after checking the active station is idle. Back up the active service files.
Do not fire a test cut solely to verify these UI changes.

## Current design and editable settings

The optional private `designs_file` is a JSON object with a `designs` mapping keyed
by stable design IDs. Each entry has `label`, `outline`, `rect`, `initial_shift`,
`settings`, and optionally `cut_job`. Settings keys are `speed_mm_s`, `interval_mm`,
`uv_duty_percent`, `frequency_khz`, and `passes`. Keep station paths, records,
Python environment, and calibration in the main configuration, not browser input.

The selector polls this catalog; the operator clicks Load design to activate an
entry. Loading and setting changes are blocked during an operation. A new design
can omit cut_job while geometry is being prepared. Use atomic catalog replacement
when publishing a new or revised design, preserve unrelated entries, and never
publish a live cut for placeholder geometry. The catalog does not run scripts.

Settings edits are preparation requests, not on-the-fly laser parameters. Save
writes an immutable request.json under records and disables the old cut. An agent
must regenerate the correct geometry/recipe and validate it before publishing the
new cut_job. Frequency/power values in the editor are requests; accepting a value
does not establish source compatibility or material suitability. The current
runner only supports its reviewed fixed source recipe and selected speeds.

When preparing whichever design the user is currently working on, publish its
outline and settings to this catalog and make it selectable. If requested settings
are unsupported by the reviewed runner, report that rather than silently running
the old values. Update cut_job hash, summary, shift and settings together. The
operator must explicitly load the revised entry; publication never starts a job.

Optional `ui_state` stores selected design, placement and pending draft atomically.
Drafts survive service restart only when the catalog definition still matches.
Historical requests and run records are preserved. Load design deliberately
discards the active draft and restores that entry's prepared settings.

`meerk40t/camera/frame_web.py` serves a local-only operator page alongside the
existing camera service. It proxies snapshots from localhost:8080 and defaults
to localhost:8081. The original camera service is not replaced.

Controls: design-axis ±X/±Y with 0.1, 1, or 10 mm steps; Save candidate; Frame
until Stop; Stop. Nudges never move hardware. Frame requires server startup with `--enable-red-framing`. The operator keeps
UV physically disabled during positioning; there is no repeated checkbox or
mandatory verbal confirmation. Standing permission covers bounded red framing
and camera checks, including placement adjustments and saving candidates. Do not
ask for frame-placement approval or repeat framing/camera permission prompts.
Engraving remains separately authorized. A camera image does not verify UV emission state.
An optional reviewed `cut_job` enables a single-pass marking endpoint. HTTP actions require a per-process token and
localhost Host header. Use verified SSH forwarding, not public port exposure.

The server loads a private configuration:

```json
{
  "outline": "/private/original-outline.json",
  "rect": [49.5, 0, 101, 120],
  "initial_shift": [0, 0],
  "records": "/private/frame-trials",
  "python": "/private/validated-environment/bin/python",
  "data_dir": "/private/reference"
}
```

These sample geometry values are not universal station defaults. Select and
review the correct original job and current placement before starting a session.
The Python environment must contain the reviewed `crs355_frame` runner. Keep
`frame_web.html` beside `frame_web.py` when deploying the standalone service.

Run `python frame_web.py --config /private/config.json --port 8081` for candidate
editing only. Explicit `--enable-red-framing` enables the bounded runner. Each
trace validates offline first, then invokes it once with --until-stopped. Existing
identity/correction checks and exclusive hardware lock remain in force.
Save and Frame each preserve a unique candidate record. Changes are in memory
until saved; server restart uses initial_shift, not the last saved candidate.

Stop sends SIGINT. The red-frame runner handles this cooperatively: it completes
the current bounded USB exchange, stops scanner moves, and acknowledges cleanup.
A clean operator stop returns the controls to Ready. An unsuccessful process or
unacknowledged cleanup still locks further runs for inspection. Cutting stop
behavior remains unchanged. It is
not a hardware emergency stop. Browser disconnect does not cancel continuous framing. Press Stop to finish;
USB operations remain timeout-bounded, and shutdown performs cleanup. Do not automatically restart a failed
trace or reset its failure state to retry.

Deployment is separate from offline testing. Start alongside the camera, forward
the new port, verify fresh snapshots and nudge round trips without clicking Frame.
No hardware commands are needed to validate the web deployment. Rollback: stop
only this web service and its tunnel; leave the original camera and records intact.

For better registration, fix the camera and workpiece, use diffuse illumination,
calibrate lens distortion and a board-plane pixel-to-mm mapping with known points,
and measure residuals at independent check points. Verify pointer-to-mark alignment
on scrap separately. A 0.1 mm nudge setting is command resolution, not achieved
accuracy. This first version translates only; it does not correct rotation or
camera perspective and does not promote a candidate to a cutting transform.

Offline tests: `python -m unittest test.test_frame_web test.test_crs355_frame`.

## Reviewed cutting from the page

The private `cut_job` configuration specifies label, summary, job path, SHA256,
exact placement shift, mark_speed (500 or 1000), reviewed runner path, and module_dir.
An optional blocked_reason disables execution and displays the unresolved issue.
The browser cannot supply arbitrary commands, job paths, speeds or pass counts.
It displays the reviewed job and requests confirmation of one pass, sending the
matching job hash. Changed frame placement invalidates the cut selection until
the geometry is regenerated and reviewed.

Before execution the server verifies file hash and runs offline validation. A
durable exclusive per-job requested marker is then written before launching the
bounded fill runner. It survives server restarts and prevents resubmission after
failure or completion. Preserve it; a new deliberate pass needs a separately
reviewed workflow. Existing controller identity, correction, hardware lock,
deadline and cleanup checks remain mandatory. Never remove blocked_reason to
work around an unresolved identity check. Web deployment tests must not invoke
the live cut action. Stop targets the active subprocess; it is not a physical
emergency stop. A browser disconnect does not cancel an already launched pass.

## Read-only cut layer progress

The camera page now includes Cut layers, current layer/card, and per-card
completion bars. GET /progress reads the selected batch manifest and preserved
run log. A card layer counts only when all its parts have verified COMPLETED
messages. Duplicate messages do not increment counts. After service restart,
the existing requested marker identifies the same run; no job is resubmitted.
Progress reports controller completion, not optical paint-removal quality.
The display polls every two seconds and labels unavailable data as stale.
Deploy backend updates only while idle; never restart the web owner during a cut.
Offline checks: python -m unittest test.test_batch_progress test.test_frame_web.


October 16 operator update: the web Frame button uses explicit --until-stopped
mode and traces until Stop. Timed CLI framing remains the default when that flag
is omitted. No automatic retry or process relaunch is used for continuous framing.

## Private Tailscale access

The web app stays bound to localhost. Tailscale Serve may proxy the private
machine hostname to localhost:8081. Add only the exact private hostname(s) to
`allowed_hosts` in the private configuration; localhost remains supported.
POST actions require both the per-process token and a matching Origin when the
browser sends one. Do not use Funnel or bind the backend to a public interface.
Anyone granted network access to this control page can operate its enabled
controls; the app currently has one shared station state, not per-user roles.

Use a persistent `laser-frame-web.service` enabled at boot instead of the earlier
transient `laser-frame-web-v1.service`. Stop the old owner only while idle.
Starting the service does not run jobs, and preserved request markers prevent
re-execution. Keep automatic service restart disabled while active-operation
recovery is not implemented. The camera and Tailscale services are independently
enabled at boot. Neither viewing nor deployment verifies optical marking.

## Toolpath animation

The camera page includes a read-only animation for the selected prepared `.lmc`
job. Play/Pause preview, Restart preview, speed, and the timeline affect only the
animation. They never POST a machine action. Orange shows marking strokes;
blue shows the current non-marking travel. One pass is shown, with the configured
pass count identified separately. The 200 mm field uses design coordinates;
curved surfaces, focus, depth, and controller delays are not simulated.

`GET /toolpath` verifies the command file against the selected job SHA256 and
extracts moves in command order. It uses the private
`data_dir/current-lightburn-JCZFiber.json` scale settings to invert the station
coordinate transform. No calibration data or file paths are returned to the UI.
A missing calibration, changed hash, unsupported manifest, or missing prepared
job displays an unavailable message rather than another design's animation.
Pending settings are labeled as the previous prepared path. Frame nudges do not
move the saved cutting path; that job must be rebuilt before cutting.

Reusable implementation: `meerk40t.camera.toolpath_preview.preview(job, data_dir)`
and `meerk40t/camera/toolpath-player.js`. Deploy both files beside `frame_web.py`
and `frame_web.html` while idle. The source image and job remain private. The
player resets when the selected design/hash changes and never auto-plays.
Tests: `python -m unittest test.test_toolpath_preview test.test_frame_web`.

## History and repeat batches

The History list contains saved framing designs and cutting batches, with request
 times and completion state. Select an entry and choose **Load selected design**.
Loading is read-only with respect to hardware; use **Frame** to project its saved
outline and **Stop** to finish before cutting. Check placement on the current
workpiece; an older position is not registration for a new board.

For a completed run, **Prepare another batch** creates and selects a new catalog
entry with a unique approval ID. It preserves the artwork, placement, speed,
frequency, duty, spacing and pass count. It does not fire. Review the displayed
summary and press **Start cutting** to execute the new batch. Original logs and
requested markers remain intact; repeated or stale preparation requests cannot
launch or duplicate a batch. Execution still revalidates the job offline.

History completion requires preserved controller-completion and clean-cleanup
records for every layer. Interrupted, missing or ambiguous records show **Needs
review** and cannot be repeated through this control. Edited settings, changed
placement, changed job hashes and blocked jobs also prevent repeat preparation.
Older custom batch formats without verifiable per-layer records remain available
for framing but require inspection and preparation through the station workflow.
The history API exposes labels, summaries, settings and request times, not private
machine paths or credentials. Loading another entry clears the previous progress
context so the page reads the selected run's records.

Offline tests: `python -m unittest test.test_frame_history test.test_frame_web test.test_web_job_controls`.
