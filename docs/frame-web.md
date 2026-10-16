# Camera page with frame steering

Operator preference (October 16): the visible page shows camera, frame nudges,
Frame, Save candidate and Stop only. Design selection, settings and cutting are
handled through chat. Their backend APIs and records remain for agent operation;
do not restore those panels unless requested. The descriptions below document
the retained backend workflow, not currently visible operator controls.

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
10 seconds; Stop. Nudges never move hardware. Frame requires server startup with `--enable-red-framing`. The operator keeps
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
trace validates offline first, then invokes it once for 10 seconds. Existing
identity/correction checks and exclusive hardware lock remain in force.
Save and Frame each preserve a unique candidate record. Changes are in memory
until saved; server restart uses initial_shift, not the last saved candidate.

Stop sends SIGINT, allowing the runner's finally cleanup to execute. An interrupted
or unsuccessful process conservatively locks further runs for inspection. It is
not a hardware emergency stop. Browser disconnect does not cancel a trace; the
runner's duration limit remains in effect. The 10 seconds excludes validation,
initialization and bounded command latency. Do not automatically restart a failed
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
