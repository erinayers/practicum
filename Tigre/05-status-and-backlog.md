# 05 — Status and Backlog

Canonical source: `src/user-story-status.json` (`last_updated: 2026-10-25`,
`current_phase: post-phase-8`, `next_recommended_story: windows-verification-of-sessions-5-and-6`).
This file is our readable summary — keep both in sync.

## Phase summary

| Phase | Title | Status |
|---|---|---|
| 1 | Strengthen the Lab Spec (metadata, docker resources, manual) | done |
| 2 | Validate / Export / Import / Preview | done |
| 3 | Runtime API + Docker control (+ ports, env, cmd, shm, mappings, host-port checks) | done (last AC of `runtime-host-port-availability` closed 2026-10-24, narrowed to Start — D-30) |
| 4 | Windows application shell (launch, local API, port-conflict UI) | done |
| 5 | Basic Designer workflows (create, nodes, networks, connect) | done |
| 6 | Student learning experience (manual flyout, progress) | done |
| 7 | Close the desktop UI gap (mockup-driven) | done 2026-10-24 |
| 8 | Windows Quick Start support + design icons | **done 2026-10-25** (54 stories total, all `done`) |

## Phase 8 — what was delivered (story by story)

| Story id | Delivered |
|---|---|
| `windows-desktop-windows-container-readiness` | Read-only engine-mode probe in the desktop (`docker_status.check_docker` → `DockerStatus.os_type/host_build/isolation`, `windows_container_readiness()` → docker_unavailable / linux_engine / ready) and in the API (`GET /docker/engine`). Create screen enables templates per engine mode; `WindowsReadinessPanel` (blocker, next action, Docker + Microsoft links, Retry); `MainWindow.refresh_engine` re-probes on Retry and each visit; chip says "Ready · Windows containers". Practicum never switches the mode. **Not Windows-verified.** |
| `designer-windows-quick-start` | Spec `Node.os`/`Node.shell` (+ validation: one OS per lab, shell fits OS, no shm/sysctls on Windows). Windows template: Server Core tag pinned from `WINDOWS_IMAGES` by the daemon host's build, PowerShell keep-alive init as `-EncodedCommand`, 2 vCPU/2 GB. Runtime: engine re-check before anything is created (structured failure with switch text), `--driver nat`, Windows note via `cmd /c type`. Gate "Container engine" check; import hands mismatches to the gate; Create re-checks readiness. `examples/windows-quickstart.json`. **Not Windows-verified.** |
| `windows-desktop-open-windows-shell` | `shell_command(container, os, shell)` from the declared fields (bash→sh / bash / sh / PowerShell / cmd), `container_state` pre-check with an actionable in-app error, **Open PowerShell** button + wording in the running view; spec field survives export/import. |
| `designer-windows-quick-start-packages` | `WINDOWS_TOOL_CATALOG` (15 Chocolatey ids) for the windows kind only, kind-aware catalog lookups, Chocolatey-id validation, per-package `choco install` in the init script with a status marker (`GET /status` note → Lab nodes table; PowerShell profile prints it); packages explicit in `environment.PRACTICUM_PACKAGES`. Ubuntu paths untouched. |
| `windows-desktop-design-icons` | `design/icons.png` sliced by `tools/slice_design_icons.py` into `assets/icons/`; `icons.py` (meanings, cached tinted/disabled QIcons, labels, rich-text img, null-safe); `MessageBanner` + icons in pills, chips, buttons, markers, cards, panels across every screen; packaging `--add-data`. Side fix: clipped error cards (Tigre/06 #25). |

## Phase 7 — what was delivered (story by story)

| Story id | Delivered |
|---|---|
| `windows-desktop-in-app-dialogs` | `confirm()` used by Reset progress, gate fixes, dashboard Delete/Reset, running-view Reset. Only native dialog: the file picker. |
| `windows-desktop-prestart-lab-gate` | `PreStartGateDialog`; re-skinned to screen-preview; Start with `wait=false` + real per-node progress (Session 5). |
| `windows-desktop-import-lab-file` | `ImportLabDialog` + samples + recent files; passes `source_file`; real start progress (Session 5). |
| `runtime-subnet-conflicts` | `/labs/{id}/networks…`, gate "Network conflicts" fixes. Windows-verified (Session 4). |
| `windows-desktop-open-node-shell` | Lab nodes table + Open shell, now inside the running view. **Not Windows-verified.** |
| `windows-desktop-labs-dashboard` | `dashboard.py` Welcome + Dashboard cards; Open / Start(gate) / Delete(confirm) / Reset(confirm). |
| `windows-desktop-lab-lifecycle-controls` | `running_view.py` toolbar: Start(gate) / Restart / Stop / Reset(danger+confirm) / Instructions; busy lock; progress while busy. |
| `windows-desktop-embedded-lab-view` | `embedded_view.py` QWebEngineView + chrome + probe/waiting + port picker + system-browser fallback. |
| `designer-visual-topology-builder` | `designer.py` three-panel screen with schematic `TopologyView`; Save Lab / Save & Start. |
| `runtime-image-pull-progress` | image inspect → explicit streamed pull → per-node progress in `/status`; `POST /start?wait=false` (202). |
| `runtime-lab-restart` (new) | `docker start` reuse after Stop (Tigre/06 #2), `POST /restart`, 409 action lock, missing-resource tolerance. |
| `runtime-delete-lab` (new) | `DELETE /labs/{id}` (reset first; 409 keeps the lab). |
| `lab-origin-and-timestamps` (new) | `origin/source_file/created_at/last_started_at/last_error` on the stored lab, excluded from export. |
| `windows-desktop-visual-theme` (new) | `theme.py` + `widgets.py`; MainWindow screen stack, title bar, status chip + connection panel. |
| `windows-desktop-create-lab-screen` (new) | screen-create: Quick start / Custom Lab cards, OS template radios. |
| `designer-quick-start-lab` (new) | screen-quickstart: templates **Ubuntu Desktop** (default; webtop in the embedded view, packages via LinuxServer mod — D-35) and **Ubuntu** (terminal; packages → apt-get command), Instructor setup, steps → manual, free `/24` from 10.90.0.0/16. Replaces the old Quick Start button. |
| `windows-desktop-status-polling` (new) | running view polls `/status` (1 s busy / 5 s idle / paused hidden). Lab nodes table shows each node's address. |
| `designer-node-catalog` (new, user feedback) | Machine presets (Ubuntu/Alpine host, Router with `net.ipv4.ip_forward` sysctl, Web server, Ubuntu Desktop, Custom image), id + address suggestions, per-network address reference. Core: `resources.sysctls` → `--sysctl`. |
| `designer-edit-existing-lab` (new, user feedback) | `PUT /labs/{id}` + designer `load_lab` edit mode; dashboard **Edit** on non-running cards (quick starts included). |
| `designer-export-spec` (UI half, user feedback) | Dashboard **Export** → save picker → portable `.json`. |

## What is NOT verified on Windows (all of Sessions 5 and 6)

Everything built on 2026-10-24/25 was verified only offscreen in the Linux sandbox — unit tests
(core 204, desktop 350), screenshot review against the mockup, scripted end-to-end runs of the
real `MainWindow` (Session 5) and of the API client (Session 6) against the live API with a
stateful fake `docker` CLI. **The next step is a Windows smoke run** with `start-practicum.bat`
and Docker Desktop:

Session 6 additions (Docker Desktop switched to **Windows containers**):

- [ ] Create New Lab in Linux mode: Windows row disabled, click it → readiness panel says
      "serving Linux containers" with the two links; Retry after switching Docker Desktop →
      row enabled, Ubuntu rows disabled, chip "Ready · Windows containers".
- [ ] Windows quick start with `git` + `7zip` and a step → Create → gate (Container engine OK,
      the multi-GB `servercore:ltsc2022` pull shows layer progress) → running view; Lab nodes
      says "running · installing…", later "tools ready"; **Open PowerShell** opens a prompt that
      prints the status; `git --version` works after the profile's PATH refresh.
- [ ] Switch Docker back to Linux containers while the lab exists → Start → gate blocks with the
      switch text; `POST /start` from Postman answers success=false with the same text.
- [ ] Import `examples/windows-quickstart.json` in Linux mode → the import dialog hands over to
      the gate instead of starting.
- [ ] Icons: crisp on a high-DPI display (125 %/150 %), visible on the dark buttons, disabled
      state legible; the packaged build (`build-windows.ps1`) ships `practicum_desktop/assets`.
- [ ] Tigre/06 #26 list (nat network + static IP, isolation mode, Chocolatey online).

Session 5 checklist:

- [ ] App opens at 1200×760 with the title bar/status chip; welcome vs dashboard decision.
- [ ] Import Existing Lab → `ubuntu-quickstart.json` → gate shows the real pull progress
      (first run) → running view opens, badge Running, Lab nodes `running`, **Open shell** works
      (`cmd /k docker exec …` — Tigre/06 #14 still unverified).
- [ ] Stop lab → Stopped badge; Start lab → gate → Running (the `docker start` path); Restart;
      Reset (confirm dialog, red) → Ready; instruction ticks survive Reset.
- [ ] `ubuntu-webtop.json`: embedded view shows the webtop desktop on 3000 (or 3001 via https);
      port picker lists both; ↗ opens the system browser.
- [ ] Create New Lab → Quick start (**Ubuntu Desktop**, the default): add `libreoffice` + a step →
      Create Lab → gate (big first pull, progress visible) → running view shows the XFCE desktop
      in the embedded view on `localhost:3000`; the package really gets installed by the
      LinuxServer mod (needs internet inside Docker; check the container log otherwise).
- [ ] Quick start (**Ubuntu**, terminal): packages + a step → running view points at Open shell;
      `apt-get` installs inside the container.
- [ ] Create New Lab → Custom Lab: Ubuntu host + **Router** preset + Alpine host on two networks
      (addresses pre-filled), Validate, Save & Start; inside host-1 `ip route add default via
      <router>` then ping host-2 across the router (the `--sysctl net.ipv4.ip_forward=1` path).
- [ ] Dashboard → **Edit** a stopped quick start lab, add a machine, Save changes → card Ready;
      **Export** → file opens in the import picker on another machine.
- [ ] Connect-form dropdown readable with Windows dark mode on (Fusion + light palette).
- [ ] Instructions flyout: drag the splitter; long lines and commands wrap; no sideways scroll.
- [ ] Probe 1 when the gate moved the subnet: the manual now says the new addresses and the Lab
      nodes Address column matches; ping between hosts succeeds.
- [ ] Dashboard: Delete (confirm) removes the lab and its containers; deleting the last lab →
      welcome screen. Error card after a failed start offers Reset.
- [ ] Connection chip: stop the API → "API unreachable", welcome with banner, Retry recovers.
- [ ] Check `pip install -e ".\desktop[dev]"` pulls PySide6-Addons (QtWebEngine) on Windows; if
      the embedded view says "not available", PySide6 was installed without the addons.

## Open gaps carried forward (from Tigre/11, still open)

1. **S-1 persistence** — labs vanish on API restart (the dashboard is empty every launch;
   Docker leftovers are handled by the gate but the root cause remains). Biggest remaining gap.
2. **S-2 / S-3** — the desktop does not start/supervise the API (only `start-practicum.bat`);
   no installer/packaging.
3. ~~S-7 edit lab~~ done 2026-10-24 (`designer-edit-existing-lab`); the "store invalid drafts" half
   remains out of scope.
4. **S-8** — designer: per-node resources/env/command editing beyond presets (metadata
   fields description/author/version now exist). ~~S-9 manual editor with preview~~ done
   2026-10-25 (Lab instructions panel in the designer, shared step editor + preview; no drag
   reordering yet). ~~S-10 export~~ done 2026-10-24.
5. **S-14** stable lab identity (`lab_key`) so manual progress survives re-import (Q-1).
6. **S-13** `.zip` bundles (the mockup still lists a `.zip`); **S-17** image inventory ("local" vs
   "will download" chips in the gate — the chip tooltip only says Docker pulls if missing);
   **S-18** cross-lab port checks; **S-19/S-20/S-21/S-22**.
7. Tigre/06 #14 Open shell on Windows unverified; #15/#16 fixed but worth a Windows look.

## Scope note (2026-10-25): Windows labs move behind the paid tier later

Windows containers need Windows Pro/Enterprise/Education, so Phase 8's Windows capabilities are
not suitable for free-plan students on Windows Home. Decision D-50: keep the implementation,
paywall it later. The how is written up as stories in
`src/future-roadmap/premium-lab-platforms/` (gating, eligibility check, hosted runtime, macOS
counterpart, authoring stays free). No code changed for this.

## Suggested order next

1. Windows smoke run when a Windows-container setup is available (above, Sessions 5 and 6).
2. Phase 9 persistence: `lab-persistence-sqlite`, then data-directory configuration and Docker
   reconciliation (implementation can begin without Windows-container hardware).
3. S-7 edit + S-10 export (closes the instructor loop from the UI), then S-8/S-9.
4. S-2 API supervision from the desktop.

## Story-status bookkeeping format (for updating `user-story-status.json`)

Each story: `{id, epic, title, status (not_started|in_progress|blocked|done), notes,
acceptance_criteria: [{text, complete}]}`. Also update top-level `last_updated`,
`latest_checkpoint` (prose), `next_recommended_story`, `current_phase`, and the phase's
`status`. The `notes` field is where implementation detail lives — keep it specific (file
names, class names, test counts), matching the existing style.


## Phase 10 ? Website backlog (planned)

Four stories define the public website scope in `src/user-stories/project-website/`: product home and audience positioning, download links to canonical GitHub releases, audience-specific getting started/help, and project transparency/contribution information. The intent is to market the free local-first application and direct users to published releases without presenting paid roadmap concepts as available. No site framework, hosting provider, or implementation has been selected.
