# Laser Pi · MeerK40t

Henry's Raspberry Pi laser station, built on the full **MeerK40t 0.9.9100**
source tree. This fork adds support for the CRS-355-5 UV source, a Pi camera
page, red-pointer positioning, and prepared cutting jobs controlled through
the web app or a Codex-assisted workflow.

## Current station

- Raspberry Pi 4 with a Raspberry Pi Camera V2.
- CRS-355-5 UV source and an EZCAD2-compatible BJJCZ controller.
- Private camera and control page available through Tailscale.
- Source-specific initialization, external lens correction, controller identity
  checks, and preserved job records.

The station uses the fork's reviewed runners and web controls. The general CRS
profile remains simulation-only; installing stock MeerK40t is not equivalent to
configuring this station. Keep version **0.9.9100** until protocol behavior is
revalidated. Historical migration notes in the detailed docs describe earlier stages.

## Using the station

Open the private station URL supplied by the owner while connected to Tailscale.
Keep the page beside Codex to inspect the camera, prepare designs through chat,
align a frame, and follow job progress.

1. **Prepare:** give Codex the artwork, physical dimensions, material, face/section,
   and intended removal areas. Review the prepared design and recipe.
2. **Align:** inspect a fresh camera image and trace the red outline. Adjust the
   position and frame again as needed. Frame continues until Stop.
3. **Run:** explicitly authorize the prepared job or use Start cutting after
   checking the job summary and coordinating with the operator at the machine.
4. **Inspect:** check layer records and the actual result before requesting more passes.

The page includes the camera, layer progress, position controls, Frame, Start
cutting, Pause, Continue, and Stop. Pause takes effect **between completed layers**
for supported batches. There is no SVG upload box; new artwork is prepared through
the workflow. Changed settings or placement require a matching toolpath.

All connected users share one station state and its enabled controls. Closing the
browser does not stop a running operation. Software Stop is not the hardware
emergency stop. The Pi must remain powered and online; the laptop need not stay
awake for the page or an already launched Pi job to remain available.

## Guides

| Task | Guide |
| --- | --- |
| Work through chat alongside the live page | [Codex and the dynamic UI](docs/codex-ui-workflow.md) |
| Give a friend access and explain controls | [Shared station quickstart](docs/friend-quickstart.md) |
| Understand the web backend and job lifecycle | [Web controls](docs/frame-web.md) |
| Inspect a fresh camera image | [Camera checks](docs/camera-check.md) |
| Position artwork using the camera and pointer | [Camera-assisted alignment](docs/camera-frame-alignment.md) |
| Understand the UV adapter and reviewed runners | [Station implementation](docs/crs355-pi.md) |
| Set up an independent development environment | [Local development](docs/local-development.md) |

## Development and verification

Clone this fork and follow [local development](docs/local-development.md) to
install it in its own virtual environment. The station regression suite runs
offline; private captured fixtures provide additional calibration/protocol checks.
Tests do not deploy, restart station services, connect to laser USB, or fire.

Our station additions live in `meerk40t/balormk/crs355*.py` and
`meerk40t/camera/`; regression tests are in `test/`. The rest of the repository
contains the upstream MeerK40t application and drivers.

Private configuration, calibration, controller identities, credentials, camera
captures, and run history stay **outside this public repository**. Cloning the
code does not grant machine access or configure another laser. Preserve completed
run markers; never automatically retry after ambiguous execution.

For PCB fabrication, the default process is **paint-resist removal followed by
chemical copper etching**, retaining resist over copper that should remain.
Software settings do not establish measured laser watts, optical pulse duration,
or full-field dimensional accuracy.

## Upstream MeerK40t

The following upstream overview is retained for general background. Its generic
installation and release advice does not replace the pinned station setup above.

MeerK40t (pronounced MeerKat) is a built-from-the-ground-up MIT licensed open-source laser cutting software.

The primary goals of this software is simple:


* Provide users with high quality laser control software.
* Provide developers with a highly extensible platform to help further their own ideas, and provide novel work to the laser community at large.

## Getting started
To get up and running, simply download Meerk40t from [here](https://github.com/meerk40t/meerk40t/releases) for your specific platform. (Windows, Mac OSX, Linux, and by extension, Raspberry Pi).

<details>
<summary>Release Versions (Just use the latest)</summary>


> * 0.9 - Active - New features and some underlying architectural changes. Try the latest released version: [0.9.9000](https://github.com/meerk40t/meerk40t/releases/tag/0.9.9000) (Jan 17, 2026) or try a prerelease even: [release list](https://github.com/meerk40t/meerk40t/releases)
> * 0.8 - Maintenance - may receive critical bugfixes but no more new features, latest version: [0.8.12](https://github.com/meerk40t/meerk40t/releases/tag/0.8.12000) (Oct 17, 2023)
> * 0.7 - Discontinued - K40 support only (including ruidacontrol emulator for 3rd party lasersoftware integration), latest version [0.7.10](https://github.com/meerk40t/meerk40t/releases/tag/0.7.10000) (June 13, 2023)
> * 0.6 - Discontinued - K40 support only, latest version: [0.6.24](https://github.com/meerk40t/meerk40t/releases/tag/0.6.24) (Oct 11, 2021)


</details>

### Command Line Interface

Meerk40t has an advanced internal console system allowing access to most parts of the code with various commands. It also provides a command line interface which should allow you to automate any processes. To learn more, download a version of Meerk40t for your platform, and execute it in a terminal with the ``--help`` argument to get a list of options.

## Compiling from source

Alternatively you can run MeerK40t directly from Python. `pip install meerk40t[all]` with python installed will usually be sufficient. Then merely run `meerk40t` at the command line.

See [Install: Source wiki page](https://github.com/meerk40t/meerk40t/wiki/Install:-Source)

The wxMeerK40t is the GUI and is written in wxPython. We use AUI to allow to have a very highly configurable UI. We can easily add panes and tools and there are quite a few available already.

## Screenshots
![grafik](https://github.com/user-attachments/assets/e56135a2-7b1f-44be-9761-b92931e300f6)

## Drivers

Meerk40t provides a variety of drivers with an extensible framework to provide support for other new laser devices. The code was written with the myriad of possibilities for different software in mind. For example, it may be essential that GRBL be able to reset an alarm or notify the user of particular error codes. The configuration for GRBL is not the same for the configuration of other laser control drivers. With this in mind, MeerK40t can radically change how and when it works


### Supported devices
*   Lihuiyu M2/M3-Nano (aka K40 lasers)
*   Any GRBL device (Atomstack, Creality, Longer, Ortur etc...)
*   Ezcad2-compatible JCZ controllers galvo lasers
*   Moshiboard
*   NewlyDraw System 8.1 Lasers
*   Ruida-Emulation (Middleman between Lightburn and K40)
