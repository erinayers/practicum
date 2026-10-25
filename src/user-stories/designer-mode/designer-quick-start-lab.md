# Quick Start Lab from a Template

## User Story

As an instructor preparing a simple exercise (or a student who just wants a sandbox),
I want to configure a single-host lab from a template — a full Ubuntu desktop in the browser for simple or non-IT labs, or a terminal-only Ubuntu — name it, choose what is pre-installed, write the steps,
so that I get a complete, startable lab without touching topology or a command line.

## Why This Matters

The mockup's `screen-quickstart` ("Configure your Quick start lab": lab name, template bar, What's included package chips, Lab instructions step editor, Instructor setup toggle) had no story, and the existing one-click Quick Start button always produced the same lab on the same subnet, colliding with itself and with the bundled sample (Tigre/06 #1, #13; Tigre/11 S-15).

## User Flow

1. From the Create New Lab screen the user picks a template and continues. **Ubuntu Desktop** (default) is a point-and-click Ubuntu desktop that opens inside Practicum's lab view — the intended choice for simple or non-IT labs; **Ubuntu** is the terminal-only container reached through Open shell; **Windows** is listed as coming soon.
2. The configuration screen shows the lab name (prefilled), the chosen template bar with "Change template", a **What's included** panel (base image chip plus removable package chips and an "Add a package" field) and a **Lab instructions** panel (numbered steps, each with a title and Markdown details, "+ Add step").
3. The **Instructor setup** toggle reveals author, version and description fields.
4. The bottom bar reads "Draft valid · 1 machine · N packages · N steps"; **Create Lab** stores the lab (origin `quick_start`) and opens the pre-start gate; on Start the running view opens with the instructions flyout.

## Functional Requirements

- Templates: **Ubuntu Desktop** (`lscr.io/linuxserver/webtop:ubuntu-xfce`, 2 vCPU / 2 GB / 1 GB shm, host ports 3000 (http) and 3001 (https), `TITLE` = lab name, image command kept so its own init runs) — the default; **Ubuntu** (`ubuntu:22.04`, 1 vCPU / 1 GB); Windows listed but disabled until the Windows Quick Start stories are complete.
- Packages are validated as Debian package names (lowercase letters, digits, `+ . -`) and de-duplicated. Terminal template: they become the node command `apt-get update && apt-get install -y <packages>` followed by `sleep infinity` (a failed install is logged but leaves the shell usable; no packages → the spec default command). Desktop template: they are installed by the image's own init through the LinuxServer `universal-package-install` mod (`DOCKER_MODS=linuxserver/mods:universal-package-install`, `INSTALL_PACKAGES=a|b|c`); the desktop ships with a browser, file manager and terminal, so its package list is empty by default.
- The running view's embedded lab view loads the desktop template's port 3000 automatically once the container answers; the terminal template has no browser port and points the student at Open shell.
- Each titled step becomes one manual section (title, Markdown details, one "Done: <title>" task) so the flyout shows numbered, checkable steps; untitled steps are ignored.
- The lab gets a free `/24` from `10.90.0.0/16` that avoids every subnet of every lab the API knows.
- An empty lab name blocks Create with an inline explanation; API validation errors are shown in the bottom bar and keep the form.
- Create goes through the same gate as any other Start (D-4); the lab is created with `origin=quick_start`.

## Acceptance Criteria

- Adding and removing packages updates the chips and the status pill; invalid names are rejected inline.
- Steps can be added, edited and removed; numbering stays contiguous.
- Create Lab produces a lab whose node runs the chosen template image with the packages wired the template's way (command for the terminal, `INSTALL_PACKAGES` for the desktop), whose manual has one section per step, and whose subnet does not overlap existing labs.
- A desktop quick start, once started, shows the Ubuntu desktop inside the running view without the student opening a browser or a terminal.
- The new lab is reviewed in the pre-start gate and, once started, opens in the running view with its steps in the instructions flyout.
- Cancel / back discard the draft.

## Edge Cases

- Every `/24` in the pool is taken — creation fails with a clear error (practically unreachable: 256 labs).
- The API rejects the definition — the bottom bar shows the field errors and Create is re-enabled.
- The template image is not local yet — the gate shows the real download progress (`runtime-image-pull-progress.md`); the desktop image is large (hundreds of MB), so the first start takes minutes.
- Host ports 3000/3001 are already taken (another desktop quick start is running) — the gate reports the port conflict and offers the recommended free ports, as for any lab.
- Package installation inside the desktop needs internet access from the container; without it the desktop still starts, without the extras.

## Implementation Notes

- `desktop/src/practicum_desktop/quickstart.py` (`QuickStartTemplate` with `kind` desktop|terminal, `TEMPLATES`, `QuickStartDraft`, `build_quick_start_lab`, `package_install_command`, `desktop_package_environment`, `steps_to_manual`, `create_quick_start_lab`), `create_lab.py` (`CreateLabScreen` template radios in a `QButtonGroup`, `QuickStartScreen`, `StepRow`), wiring in `main_window.py::_on_quick_start_create`.
- Decision D-35 (Tigre/09): the desktop template is the default because it is the friendliest start for the non-IT audience; the terminal template stays one click away.
- Absorbs the second half of Tigre/11 S-15 and fixes Tigre/06 #1 (D-17 now wired). Windows support is planned in `designer-windows-quick-start.md`, `windows-desktop-windows-container-readiness.md`, `windows-desktop-open-windows-shell.md`, and `designer-windows-quick-start-packages.md`. Practicum must check readiness and guide the user; it must not silently switch Docker Desktop's global engine mode.
- Reference design: `screen-quickstart` in `design/practicum-mockups.html`.

## Implementation Status

Done 2026-10-24 (Session 5); **Ubuntu Desktop template added the same day** at the user's request ("a simple image for simple or non-IT related labs"). Tests: `desktop/tests/test_quickstart.py` (incl. the webtop definition and the package mod), `desktop/tests/test_create_lab.py`, `desktop/tests/test_main_window.py`. Verified end-to-end with the fake `docker` CLI for both templates: the desktop quick start created with `libreoffice` and one step → gate → running view showing `http://localhost:3000` in the embedded view and the step in the flyout. Not yet run against real Docker Desktop (the real webtop image needs a multi-hundred-MB pull and internet inside the container for `INSTALL_PACKAGES`).

## Update 2026-10-24 (user feedback: "git was claimed installed but not recognised"; "give a list of popular software")

- **Popular software picker**: "What's included" now shows a curated, per-template list of toggle chips (`quickstart.PACKAGE_CATALOG`: terminal — git, python3 (+pip), nodejs (+npm), java, build-essential, curl, wget, jq, nano, vim, ping, ip tools, net-tools, traceroute, tcpdump, nmap, ssh, sqlite3; desktop — git, python3, nodejs, java, curl, wget, jq, sqlite3, libreoffice, gimp, inkscape, vlc, audacity, thunderbird, filezilla, keepassxc, vscodium), each with a one-line description; an "Other packages" field still accepts any Ubuntu package name. The terminal template preselects git, python3 and curl; the desktop preselects nothing.
- **Visible install progress**: installing takes a minute or two after the first start, which is why a shell opened right away did not know `git`. The terminal template's start script now keeps a one-line status marker (`/run/practicum-packages.status`: "installing …" → "packages ready" / "install FAILED (is the container online? see /var/log/practicum-packages.log)"); `GET /status` reads it (`RuntimeResourceStatus.note`, one `docker exec cat` per running container per poll), the Lab nodes table shows `running · installing…` / `running · install failed` with the full line under the table, and Open shell now starts a *login* shell (`bash -l` / `sh -l`) so the same line is printed when the terminal opens. The picker also says so ("Installing takes a minute or two after the lab starts…"). The desktop template's LinuxServer mod has no such marker yet (its progress is in the container log).
