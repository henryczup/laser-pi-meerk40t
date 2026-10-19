# Using Codex with the live station page

Use chat to describe and prepare the work, and keep the camera/control page beside
it to inspect the result. The page is a live view of the Pi's selected job, not a
separate design editor. Changing a design in chat only changes the station after
Codex explicitly prepares and publishes it.

## Open the workspace and page

1. Open the active `laser-pi-meerk40t` checkout in Codex. On Henry's laptop it is
   `C:/Users/henry/dev/laser-pi-meerk40t`.
2. Connect Tailscale and open the private station URL supplied by the owner. Ask
   Codex to open it beside the chat, or use your normal browser.
3. Ask Codex to check the current job and connection before continuing an old task.
   Use the camera timestamp to distinguish a fresh image from a stale preview.

Henry's installation has the `laser-pi-control` skill, which routes to this repo's
workflows. On another computer, cloning the repo does not install that skill or
grant SSH/Tailscale access. Supply the repo instructions and arrange access with
the owner; never copy the owner's credentials into chat or Git.

The webpage can stay available while the laptop sleeps because the Pi hosts it.
That does not mean Codex is continuously watching the page or that a local Codex
session keeps working while the laptop sleeps.

## Prepare a design through chat

Attach an SVG to the conversation or provide an accessible file path. Include
physical dimensions, material, which face/section to process, and what should be
removed versus retained. There is no SVG upload box on the current page.

Example:

> Prepare this SVG for paint-resist removal on my board. Keep the artwork at its
> stated size. Show me the removal geometry and publish a framing candidate.
> Do not cut yet.

Codex should inspect the geometry, prepare the toolpath offline, and publish the
outline, placement and job summary to the private design catalog. Changing speed,
line interval, placement or pass count requires a matching prepared job; changing
text in chat is not enough. Preserve unrelated catalog entries and run records.

## Align using the camera and frame

Example:

> Check a fresh camera image, frame the selected design, and line it up with a
> small margin on the right edge. Do not cut yet.

Codex checks a fresh camera image before reporting physical alignment. The camera
cannot establish UV emission state or measured red-to-UV accuracy. Keep UV
emission physically disabled while positioning the workpiece. Existing standing
permission covers camera checks and red framing; it does not authorize cutting.

The page's Step and ±X/±Y controls change the candidate offset in design axes,
which may differ from screen left/right. They do not move a physical stage.
Stop an active frame before changing its position, then frame again. Frame runs
until Stop. Save candidate records the placement; it does not approve a cut.
After moving the board by hand, tell Codex to inspect it again.

## Start and monitor a prepared job

Once alignment and the prepared recipe are agreed, give an explicit instruction:

> Run one pass of the currently prepared design at the approved placement.

Or click **Start cutting** after checking the displayed job summary and arranging
machine readiness with the operator. Do not both click Start and ask Codex to
start the same job. Everyone connected shares the same station state; agree who
has control before operating it.

| Page control or display | Meaning |
| --- | --- |
| Camera timestamp | Time the browser received the image; check freshness before relying on it. |
| Job summary | The selected prepared design and recipe, not necessarily the last design mentioned in chat. |
| Cut layers | Completed layers reported from run records for the selected job. “Card 1” may label a single non-card workpiece. |
| Pause | Requests a pause after the current layer for a supported batch; it is not an immediate beam pause. |
| Continue | Resumes remaining layers of that paused batch. It does not restart a completed or stopped job. |
| Stop | Requests software cancellation of the active operation; it is not the hardware emergency stop. |

The UI polls status and layer progress automatically. “All layers completed”
reports controller completion of the selected job, not verified paint clearance
or the total passes across all earlier jobs. Ask Codex to check both logs and a
fresh camera image when assessing the result.

For additional passes, specify the count and any recipe change. Codex prepares a
new bounded request with new records; it must not erase completed-run markers.

## Disabled controls and connection problems

Disabled controls can mean a running operation, a pending action, a completed or
failed request, an unprepared design, or unsupported pause/continue behavior.
Ask Codex to read the status and relevant run log rather than bypassing the check.

> Check why Start is disabled and explain the current job state. Do not start or
> retry anything.

Closing the page or losing Tailscale does not cancel an already running job or
continuous frame. Reconnect and inspect status before acting. After an ambiguous
failure, never assume that nothing ran and automatically retry. Preserve records.

## Requesting UI changes

Describe the exact control or panel to change, with a screenshot if useful.
Codex should edit the repo, validate offline, and distinguish local changes from
what is deployed on the Pi. Restarting the service during a job is not an offline
test. A UI update does not authorize a test engraving.

See [web implementation](frame-web.md), [camera alignment](camera-frame-alignment.md),
[station controls](crs355-pi.md), and [friend quickstart](friend-quickstart.md).
