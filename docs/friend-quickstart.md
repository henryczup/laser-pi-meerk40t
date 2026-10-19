# Shared laser station quickstart

## Connect

1. Install [Tailscale](https://tailscale.com/download) on your phone or computer.
2. Sign in with your own account and accept the station owner's machine-sharing invitation.
3. Turn on Tailscale and open the private camera/control URL supplied by the owner.

The Raspberry Pi hosts the app. The owner's laptop need not remain awake, but
the Pi must remain powered and connected. The URL alone does not grant access.
Do not use the owner's credentials or publish an invitation link.

## Operate together

For chat-driven design preparation and the live side panel, follow
[Using Codex with the live station page](codex-ui-workflow.md).

Agree who is controlling the station before changing anything. All browsers
share one selected design, position and running job; there are no separate
viewer/operator accounts in the app. Arrange for an operator at the machine
before engraving, with the material and machine ready.

- **Camera:** check the image timestamp. A stale or missing image is not a live view.
- **New designs:** send the SVG to the station owner for preparation; the page
  does not have an upload box. A design must be prepared before it can run.
- **Position controls:** adjust the candidate frame placement. Review the outline
  and job summary together; changing placement may require rebuilding the cut.
- **Frame:** traces the red outline until **Stop**. Keep UV emission physically
  disabled while positioning the workpiece.
- **Start cutting:** executes the selected, prepared job. Check its name, material,
  placement and settings first. A completed job cannot simply be started again;
  additional passes need a newly prepared request.
- **Pause:** requests a pause after the current layer, for supported batches only.
- **Continue:** resumes the remaining layers of that paused batch.
- **Stop:** requests software cancellation. It is not the machine's emergency stop.

Closing the browser or losing network access does not stop an already running
operation. After an interrupted or failed request, inspect its records before
another run; do not clear completion markers or blindly retry.

For PCB work, our default process removes paint resist before chemical copper
etching. It is not a direct copper-cutting recipe.

## Source and workflows

- [Source repository](https://github.com/henryczup/laser-pi-meerk40t)
- [Web controls](frame-web.md)
- [Camera alignment](camera-frame-alignment.md)
- [Station adapter](crs355-pi.md)
- [Local development](local-development.md)

Private calibration, identity records, credentials and run history are not in
the public repository. Cloning the code does not configure another machine.

## Owner: grant or revoke access

In the Tailscale admin console, share the Pi machine with the friend's account,
rather than inviting them to administer the entire network. Network policy also
governs the services they can reach; machine sharing is not a camera-only role.
The current web app grants access to all enabled controls. Revoke the machine
share when access is no longer needed.

See [Tailscale's machine-sharing instructions](https://tailscale.com/docs/features/sharing).
