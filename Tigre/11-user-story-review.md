# 11 — User Story Review: Gaps and Improvements

Review date: 2026-10-23. Scope: all 38 stories in `src/user-stories/`, `src/user-stories.md`,
and `src/user-story-status.json`, evaluated against the actual code. Nothing in `src/` was
modified; this is a proposal. Priorities: **P0** = blocks the product's own "First Product
Slice" or a Phase-7 story; **P1** = needed for a credible student/instructor experience; **P2** =
quality/robustness; **P3** = nice to have.

---

## 1. Executive summary — the ten things that matter most

| # | Finding | Kind | Priority |
|---|---|---|---|
| 1 | **The instructor → student loop cannot be completed from the UI.** There is no way to export a lab to a file from the desktop (only `GET /export` exists), no manual editor, no metadata/resource authoring in the Designer. Stories `designer-export-spec`, `designer-author-manual` are marked *done* on the strength of API/spec work alone. | AC debt + missing stories | P0 |
| 2 | **Students have no way to use a CLI lab node.** The core use case is *networking* labs (routers, `ping`), yet the only documented way to reach a container is `docker exec` in a terminal — contradicting the "no Docker commands" promise. No story covers an in-app terminal / "Open shell" per node. | Missing story | P0 |
| 3 | **Students must start the API themselves** (`uvicorn …` is the literal "next action" text). No story covers launching/bundling the API with the desktop app or installing the product. | Missing story | P0 |
| 4 | **Labs vanish on API restart**, but the Labs Dashboard story is written for "returning users". No persistence story exists. | Missing story / contradiction | P0 |
| 5 | **Labs Dashboard claims "backed entirely by existing endpoints"** — but needs `DELETE /labs/{id}` (doesn't exist), a Draft/origin/last-run concept (not in the model), and an `error` status mapping (undefined). | Story inaccuracy | P0 |
| 6 | **Restart is undefined** and stop→start is (likely) broken in the runtime (Tigre/06 #2). `lab-lifecycle-controls` lists Restart with no backend semantics. | Ambiguity + bug | P1 |
| 7 | **Import auto-start skips the "see what will run on my machine" gate.** `prestart-lab-gate` says it gates *every* Start; `import-lab-file` bypasses it for conflict-free labs. A student opening a file from anywhere gets arbitrary containers started with no review. | Contradiction / trust | P1 |
| 8 | **Six stories' ACs differ between the markdown and the JSON tracker**; several "done" ACs describe desktop behaviour that doesn't exist (e.g. "Desktop UI refreshes status" — the desktop never calls `/status`). | Process | P1 |
| 9 | **Port checks miss three cases that stories list as requirements**: other *defined* labs' ports (FR, untracked), UDP (probed with TCP), and re-verification immediately before Start (edge case in 3 stories, never an AC). | AC debt | P1 |
| 10 | **Mockup screens with no story**: `screen-create` / `screen-quickstart` (OS templates, package picker, step editor) and the existing Quick Start button (`quickstart.py`) have no backing story at all. | Missing story | P2 |

---

## 2. Process and format issues

### 2.1 Markdown ↔ JSON acceptance-criteria drift

The JSON is what gets ticked; the markdown is what gets read. They disagree for 6 stories.
(False positives from quote/hyphen differences excluded.)

| Story | md ACs | JSON ACs | AC present only in markdown |
|---|---|---|---|
| `windows-desktop-labs-dashboard` | 6 | 5 | "Canceling a delete confirmation leaves the lab list unchanged." |
| `windows-desktop-prestart-lab-gate` (**done**) | 5 | 4 | "The manual's step count/preview is visible from this screen." (met — count only) |
| `windows-desktop-import-lab-file` | 5 | 4 | "The imported lab appears in the Labs Dashboard list afterward, whether or not it was started." |
| `windows-desktop-lab-lifecycle-controls` | 5 | 4 | "Canceling the Reset confirmation leaves the lab running and unchanged." |
| `designer-visual-topology-builder` | 5 | 4 | "Removing a machine, network, or connection updates all affected panels immediately." |
| `runtime-image-pull-progress` | 5 | 4 | "Existing start/status/stop/reset behavior and endpoints are otherwise unchanged." |

**Fix:** make the JSON the single source of ACs (or generate it from the markdown). Add the
missing ACs to the JSON now — they are all good criteria.

### 2.2 Inconsistent story template

- 6 runtime stories (`runtime-browser-accessible-nodes`, `-browser-desktop-example`,
  `-node-command-options`, `-node-environment`, `-port-mappings`, `-shared-memory`) have no
  *User Flow*, *Edge Cases* or *Implementation Notes* and carry an in-file `## Status: Done`
  that duplicates (and can drift from) the JSON.
- `user-stories.md` "Recommended Story Order" lists 29 stories; the JSON tracks 38. The 9
  untracked-in-order stories (`windows-desktop-port-conflict-ui`, the 8 runtime-* additions)
  have no place in the phase narrative. The older "Suggested MVP Backlog" list is superseded and
  now misleading (items 8 and 10 are now Phase 7).
- `latest_checkpoint` in the JSON says `windows-desktop-in-app-dialogs` is done; its `status` is
  `in_progress`.

### 2.3 "Done" means "API done" for several user-facing stories

The project pattern has been: implement the API, tick the story, and say "the desktop will do
the UI in a later story". That is fine **only when the later story exists**. Table of ACs ticked
complete whose behaviour is absent in the desktop app and **has no follow-up story**:

| Story (done) | AC / FR ticked complete | Reality | Follow-up story exists? |
|---|---|---|---|
| `designer-author-manual` | "instructor can create manual sections"; "write formatted content"; "preview the manual as a student would see it" | No manual editor anywhere in the Designer | **No** |
| `designer-export-spec` | "The app exports a portable JSON spec file"; "export validates before completion" | No export/save-as in the desktop; only `GET /labs/{id}/export` | **No** |
| `designer-validate-lab` | "Export is disabled or discouraged when validation fails" | No export in UI to disable | **No** |
| `lab-spec-metadata` | User flow: "instructor enters name, description, author, version" | Designer has `name` only | **No** |
| `lab-spec-docker-resources` | "Each node can optionally specify CPU/memory/ports" (as instructor action) | Designer has id + image only; no resources, env, command | **No** |
| `designer-create-new-lab` | FR "The draft tracks unsaved changes" | Not implemented (notes admit) | **No** |
| `designer-add-nodes` / `-networks` / `-connect` | FR "add, **edit**, and remove" | Remove only; no edit (mockup shows ✎) | Partly (`visual-topology-builder` doesn't mention edit) |
| `runtime-api-status` | "Desktop UI refreshes status" | Desktop never calls `GET /status`; list shows cached `status` string from `GET /labs` | **No** |
| `runtime-host-port-availability` | FR "detect host ports already assigned to other known labs" | Not implemented; only same-lab duplicates + API port + OS bind | **No** |
| `runtime-host-port-recommendations` | FR "suggest available UDP ports when needed" | UDP probed via TCP bind | **No** |
| `windows-desktop-port-conflict-ui` | Impl note: "integrated into both Designer Mode and Student Import" | Designer has no port fields | **No** |
| `student-stop-lab`, `student-reset-lab` | "student can stop…"; "app warns before reset" | No Stop/Reset in desktop | Yes — `lab-lifecycle-controls` |
| `student-import-spec` | "student can select a spec file from disk" | No file picker | Yes — `import-lab-file` |
| `windows-desktop-prestart-lab-gate` | FR "Images already present locally are visually distinguished from images that will be pulled" | Not possible — API has no image info | Partly — `image-pull-progress` (different scope) |

**Recommendation:** either (a) re-open these ACs, or (b) keep them and add the follow-up stories
in §5 so the debt is tracked. (b) is less disruptive; the stories in §5 are written to absorb
exactly these ACs.

---

## 3. Contradictions and ambiguities between stories

| # | Stories | Conflict | Suggested resolution |
|---|---|---|---|
| C1 | `prestart-lab-gate` ("single mandatory screen that gates every Start action, regardless of where triggered") vs `import-lab-file` ("conflict-free import proceeds straight to the running view") | Import bypasses the review of images/resources/topology. Product decision D-2 was taken for convenience, but the gate's own "Why" is "never start a lab blind". | Keep auto-start but show the gate's summary *inside* the import progress overlay (name, images, CPU/mem) with a 1-click "Review first" escape, **or** auto-start only for labs imported from a trusted/recent list. Record the outcome in Tigre/09. |
| C2 | `prestart-lab-gate` user flow lists "the Designer's **Save Lab** action" as a Start entry point; `designer-create-new-lab` says Save stores a draft | Does saving a lab start it? Mockup `screen-custom` "Save Lab" → `screen-preview` suggests yes. | Decide: Save = store + go to dashboard (recommended), with an explicit "Save & Start" secondary action. |
| C3 | `labs-dashboard` defines **Draft** = "saved but never successfully started/validated", and "only Edit/Delete until it validates" | `POST /labs` rejects invalid specs, so every stored lab is validated; "unvalidated draft" cannot exist. The API statuses are `defined/starting/running/stopping/stopped/error`; the story uses Running/Stopped/Draft. `error` has no UI mapping anywhere. | Define the mapping explicitly: `defined`→"Ready" (or "Draft" if never started), `stopped`→Stopped, `running`→Running, `starting/stopping`→busy, `error`→Error with "Reset" CTA. Drop "not yet validated" unless invalid drafts become storable (see S-7). |
| C4 | `labs-dashboard` cards show origin ("Imported from x.zip", "Quick start", "Custom lab") and "Last run yesterday" | Neither origin nor timestamps exist in `Lab`/`LabDefinition`; the story says "no backend changes". | Add `origin` + `created_at/last_started_at` to the stored `Lab` (not the portable spec) — see S-5. |
| C5 | `labs-dashboard` "Deleting a lab … removes it" | No `DELETE /labs/{id}`; story says desktop-only. | Add S-4 backend enabler. |
| C6 | `lab-lifecycle-controls` offers **Restart** | No API semantics for restart; `runtime-api-stop-lab` says stop may keep containers; stop→start likely fails (Tigre/06 #2). | Define Restart = `stop` + `start` at the service level (`POST /labs/{id}/restart`) and fix start-after-stop to `docker start` existing containers. See S-6. |
| C7 | `student-stop-lab` impl note: "Decide later whether networks remain after stop" | Never decided; runtime keeps networks on stop, removes on reset. | Record as decision (current behaviour is fine). |
| C8 | `import-lab-file` accepts `.json` **or `.zip`** | Nothing defines a zip format; the API only accepts JSON. | Either drop `.zip` from the story or add S-13 defining a bundle format. |
| C9 | `windows-desktop-launch` next action = "Start the Practicum API with `uvicorn practicum.main:app --reload`" vs product vision "no command-line tooling required" | Students cannot be expected to run uvicorn. | S-2 (API lifecycle). |
| C10 | `manual-track-progress` edge cases "instructor provides a new version of the same lab / sections reordered" | Progress key is `lab_id` (a per-import uuid) — re-importing the same lab **always** loses progress, regardless of versioning. | Key progress by a stable spec identity (e.g. hash of name+author+version, or a new `lab_key` in the spec) — see S-14. |
| C11 | `runtime-host-port-availability` user flow "blocks validation/**export**/start" | Export is portable; host ports are machine-specific. Blocking export on a local conflict is wrong. | Change the last AC to "start" only, mark the story done (Q-2 in Tigre/09). |
| C12 | `designer-visual-topology-builder` — "no changes to validation or the underlying data model" | Fine, but the mockup's cards show a *role* (host/gateway) per machine that the model doesn't have. | Note in story: role is derived (≥2 interfaces ⇒ "gateway") or out of scope. |

---

## 4. Story-by-story improvement notes (existing stories)

### Phase 7 (active)

**`windows-desktop-in-app-dialogs`** — Good. Add: an in-app *error* dialog/banner component is
implied ("error messages appear as in-app banners… never as native") but only `confirm()` exists;
add an AC for a non-blocking error/info banner component so Start/Import failures have a
sanctioned home. Add edge case: a worker finishes while a modal is open.

**`windows-desktop-labs-dashboard`** — Fix C3/C4/C5. Add ACs: "the dashboard reflects live
status via `GET /labs/{id}/status` on show (stale-Running edge case)"; "a lab in `error` offers
Reset"; "labs with the same name are distinguishable". Make its dependencies explicit:
S-4 (delete), S-5 (origin/timestamps), S-1 (persistence — otherwise the dashboard is empty at
every launch, which defeats its purpose).

**`windows-desktop-prestart-lab-gate`** (done) — Two FRs are unmet (image local/pull flag; manual
*preview*, not just count). Move them into S-9 (image inventory) and a small follow-up
("manual preview from the gate"), and mention that in the story notes so the debt is visible.
Add the missing "re-verify ports on Start" AC (currently an edge case only).

**`windows-desktop-import-lab-file`** — Resolve C1, C8. Decide duplicate-import behaviour (Q-1).
Add AC for a non-JSON/oversized file (size limit), and for the API-unreachable case (currently an
edge case). Define what "recent/sample files" list is backed by (S-15 bundled samples + QSettings
recent list).

**`windows-desktop-lab-lifecycle-controls`** — Resolve C6. Add AC: "controls are disabled while
a lifecycle call is in flight" (edge case → AC). Add AC: partial reset failure is shown with the
per-resource result from `RuntimeActionResult.errors` / `status`. Specify where Start lives
for a *stopped* lab in the running view (toolbar shows Restart/Stop; after Stop the view should
offer Start via the gate).

**`windows-desktop-embedded-lab-view`** — Missing edge cases: (1) webtop serves **HTTPS with a
self-signed cert** on 3001 — `QWebEngineView` will refuse it unless certificate errors are
handled for localhost; (2) HTTP vs HTTPS choice per port is unknown to the app (spec has no
scheme) — add an optional `scheme`/`url_path` hint to `PortMapping` or probe; (3) `localhost`
vs `127.0.0.1`; (4) QtWebEngine adds ~150 MB to the install — confirm acceptable. Add AC for a
"waiting for service" state with retry (currently FR only).

**`designer-visual-topology-builder`** — Add *edit* of existing machine/network/connection (FR
from the original stories, never delivered). Clarify "role" (C12). Consider folding S-8
(metadata/resources authoring) in, since the card layout is where those fields belong.

**`runtime-image-pull-progress`** — Clarify the API contract: `POST /start` becomes async
(returns 202 + status `starting`) — that changes existing tests and the desktop `start_lab`
semantics; the story says "endpoints otherwise unchanged", which is not quite true. Add ACs:
"start is rejected/ignored while a start is already in progress" (action locking) and "cancel
an in-progress start" (edge case from `student-start-lab`). Split into two stories: (a) async
start + per-node status + locking, (b) pull progress parsing. (a) alone fixes Tigre/06 #3.

### Earlier phases (done) — small edits worth making

- `windows-desktop-launch` / `windows-desktop-local-api` (done): observed false "Blocked" on a
  loaded machine (Tigre/06 #11). Add ACs: "startup health check retries with backoff before
  reporting Blocked"; "a timeout is worded differently from a refused connection"; "the Blocked
  state auto-retries periodically". The edge case "API starts after the desktop app has already
  opened" is listed but has no AC — make it one.
- `runtime-api-status`: add "the API can reconcile/rediscover lab state from Docker labels after
  a restart" as a future AC or move to S-1.
- `designer-add-networks`: edge case "two networks use overlapping subnets" → make it a real AC
  (within a lab: validation error; across labs: warning) — see S-10.
- `designer-connect-nodes-networks`: edge case "network or broadcast address" → make it an AC
  (the model currently accepts `10.0.1.0/24` and `10.0.1.255/24` as interface addresses).
- `lab-spec-docker-resources`: `exposed_ports` vs `port_mappings` are two ways to say one
  thing; plan to deprecate `exposed_ports` in schema 1.1 or document when to use which.
- `windows-desktop-local-api`: edge case "API returns a version the client does not understand"
  → AC: `GET /health` returns `version`, client warns on mismatch (cheap, do it in S-2).

---

## 5. Missing stories (proposed)

Each is written so it could be dropped into `src/user-stories/<epic>/` with the existing
template. Epics in brackets; new epic suggested where none fits.

### S-1 · Persist labs across API restarts — [Docker Runtime API] · **P0**
*As a returning user, I want my labs to still be there when I reopen Practicum.*
ACs: labs survive API restart (JSON file store under a per-user data dir, e.g.
`%LOCALAPPDATA%\Practicum\labs\`); lab `status` is reconciled against Docker on load (labels
`practicum.lab_id`); a corrupt store file is reported, not fatal; in-memory mode remains for
tests. Unblocks: dashboard, import-and-resume, progress keys.

### S-2 · Desktop launches and supervises the local API — [Windows Desktop Application] · **P0**
*Interim (2026-10-23): `start-practicum.bat` at the repo root starts both processes and stops the
API when the desktop closes. It is a developer/launcher convenience, not the in-app supervision
this story describes.*
*As a student, I want Practicum to start its own backend so I never run a terminal command.*
ACs: on launch, if `GET /health` fails the desktop starts the API as a child process on a free
port (sets `PRACTICUM_API_PORT`) and waits for health; the API is stopped when the desktop
exits; the "Blocked" state only remains for a genuinely failed spawn, with the log excerpt
shown in-app; `GET /health` returns `version` and the client warns on mismatch; the manual
"uvicorn" next-action text is gone. Also covers binding the API to `127.0.0.1` only (NFR).

### S-3 · Package and install the product on Windows — [Windows Desktop Application] · **P0**
ACs: a single installer/portable build (PyInstaller or MSIX) containing desktop + API;
first-run screen detects Docker Desktop and links to install guidance; app version visible in
the UI; uninstall leaves labs/progress unless asked. (Without S-2/S-3 every "student" story is
hypothetical.)

### S-4 · Delete a lab through the API — [Docker Runtime API] · **P0** (dashboard enabler)
ACs: `DELETE /labs/{id}` removes the lab (404 if missing); if the lab has runtime resources,
the API resets them first or returns 409 with a clear message (decide); deleting clears nothing
outside Practicum; `ApiClient.delete_lab` exists with tests.

### S-5 · Lab origin and activity timestamps — [Lab Spec Format] · **P1** (dashboard enabler)
ACs: stored `Lab` carries `origin` (`imported` | `quick_start` | `designer`), `source_file`
(optional), `created_at`, `last_started_at`; these are **not** part of the exported spec;
`GET /labs` returns them; dashboard cards render them.

### S-6 · Restart lab and start-after-stop — [Docker Runtime API] · **P1**
ACs: starting a `stopped` lab reuses its existing containers (`docker start`) rather than
failing on name conflict; `POST /labs/{id}/restart` = stop + start with a single structured
result; lifecycle calls on a lab already `starting`/`stopping` are rejected with 409 (action
lock); tests cover stop→start→running.

### S-7 · Edit an existing lab in the Designer — [Designer Mode] · **P1**
ACs: `PUT /labs/{id}` replaces the definition (validated; rejected with 409 while running);
the dashboard "Edit" opens the Designer pre-populated; nodes/networks/interfaces can be edited
in place (not just removed), with reference cascade explained; unsaved-changes guard on close
(in-app dialog). Optionally allow storing *invalid drafts* locally (desktop-side file) so "Draft"
in C3 becomes real.

### S-8 · Author metadata, resources, environment and command in the Designer — [Designer Mode] · **P1**
ACs: description/author/version fields; per-node CPU, memory, shm, port mappings (with
protocol), environment variables, command mode (default `sleep infinity` / image default /
custom); inline port-conflict check in the node editor (closes the `port-conflict-ui` note);
Validate/Save unchanged. Absorbs the unmet FRs of `lab-spec-metadata` and
`lab-spec-docker-resources`.

### S-9 · Author and preview the lab manual in the Designer — [Designer Mode] · **P0**
ACs: add/reorder/delete sections; markdown editor with live rendered preview identical to the
student flyout; add/remove checkable tasks with auto-generated stable ids; stored in the spec
on Save. Absorbs `designer-author-manual` ACs. Mockup reference: `screen-quickstart` step
editor.

### S-10 · Export a lab to a file from the desktop — [Designer Mode] · **P0**
ACs: "Export…" on the dashboard/designer calls `GET /labs/{id}/export` and writes
`<name>.json` via the OS save dialog (the second sanctioned native dialog — update
`in-app-dialogs` accordingly); warns (doesn't block) on local port conflicts (resolves C11);
overwrite confirmation in-app; file round-trips through import unchanged (test).

### S-11 · Open a shell into a lab node — [Windows Desktop Application] · **P0**
*As a student in a networking lab, I want to open a terminal on `router` from the app.*
ACs: running view lists nodes; "Open shell" launches `docker exec -it <container> <shell>` in an
in-app terminal widget (or, MVP, in Windows Terminal/conhost via `subprocess`), choosing
`bash`→`sh` fallback; works for nodes without port mappings; the embedded-lab-view node picker
and this share one "node" concept. This is the CLI counterpart of `embedded-lab-view` and is
essential for the stated core use case.

### S-12 · Status polling and reconciliation in the desktop — [Windows Desktop Application] · **P1**
ACs: running view polls `GET /labs/{id}/status` (e.g. every 3–5 s) and shows per-container
state; containers that died outside Practicum flip the badge and offer Reset; polling pauses
when the view is hidden. Prerequisite for `image-pull-progress` UI and the dashboard's
stale-status edge case. Absorbs the `runtime-api-status` "Desktop UI refreshes status" AC.

### S-13 · Lab bundle (.zip) format — [Lab Spec Format] · **P2** (or delete `.zip` mentions)
ACs: `lab.json` + optional `assets/` (files to copy into nodes?) + manual images; import
extracts and validates; export produces it when assets exist. If not wanted now, remove `.zip`
from `import-lab-file` and the mockup.

### S-14 · Stable lab identity for progress and re-import — [Lab Manual Flyout] · **P2**
ACs: spec gains optional `lab_key` (uuid set by the Designer on first save, preserved across
export/import); manual progress keys use `lab_key` when present; importing a file with the
same `lab_key` offers "resume existing" vs "import as copy" (closes Q-1); different `version`
with same key keeps progress for unchanged task ids.

### S-15 · Bundled sample labs and Quick Start templates — [Student Import Mode] · **P2**
ACs: the examples ship inside the desktop package and appear in the import picker's "sample"
list; Quick Start offers the templates from the mockup (Ubuntu now; Windows marked "coming
soon"), picks a free subnet from `10.90.0.0/16` (fixes Tigre/06 #1); optional package
pre-install list becomes a documented `command`/`environment` pattern or is dropped from the
mockup.

### S-16 · Subnet conflict detection — [Docker Runtime API] · **P2**
ACs: validation rejects overlapping subnets *within* a lab; `GET /labs/{id}/ports`-style check
(or a new `/labs/{id}/networks`) warns when a subnet overlaps another defined lab or an existing
Docker network; the gate shows it with a "pick a free subnet" recommendation.

### S-17 · Image inventory before start — [Docker Runtime API] · **P2**
ACs: preview (or `/labs/{id}/images`) reports per image: present locally (`docker image
inspect`), size when known; the gate flags "will download"; unmet FR of `prestart-lab-gate`.
Natural precursor to `image-pull-progress`.

### S-18 · Port checks: cross-lab, UDP, and re-verify on Start — [Docker Runtime API] · **P1**
ACs: ports mapped by other defined (not just running) labs are reported as
`used_by_other_lab` with the lab name; UDP ports are probed with UDP; `POST /start` re-checks
ports and returns a structured `port_conflict` failure instead of letting Docker fail. Closes
three open FR/edge-case items.

### S-19 · Host resource feasibility — [Docker Runtime API] · **P3**
ACs: `docker info` memory/CPU are compared with the lab's estimate; the gate shows a warning
(not a block) when the lab exceeds ~80 % of host memory.

### S-20 · Diagnostics and logs — [Windows Desktop Application] · **P2**
ACs: the API writes a rolling log file; every failed runtime action offers "Copy details"
(message + docker command); a "Show logs" action opens the log folder; no secrets (env values)
are logged.

### S-21 · Public lab spec reference — [Lab Spec Format] · **P2**
ACs: `docs/lab-spec.md` (or README section) documents every field, defaults, validation rules,
and a changelog per `schema_version`; import rejects unknown **major** versions with a clear
message (C-level edge cases in 3 stories). The roadmap promises "public spec format and
documentation" and nothing delivers it today.

### S-22 · Cross-cutting non-functional requirements — new short doc, not a story · **P2**
Capture once: UI never blocks > 100 ms (worker rule); API binds loopback only; per-call
timeouts (long for start/stop/reset); window minimum size / DPI; Windows-specific port ranges
(Hyper-V reserved) explained in conflict text; accessibility basics (keyboard navigation of
dialogs).

---

## 6. Suggested Phase 7 re-sequencing (with the gaps folded in)

The current Phase 7 order is UI-first; several items will stall on missing backend pieces.
Proposed order:

1. **Backend enablers (small, testable):** S-4 delete · S-6 restart/start-after-stop + action lock ·
   long timeouts for lifecycle calls (Tigre/06 #3) · S-5 origin/timestamps · `version` in `/health`.
2. **S-1 persistence** — before the dashboard, or the dashboard will be empty every launch.
3. `windows-desktop-labs-dashboard` (restructure MainWindow into screens) + S-12 status polling.
4. `windows-desktop-lab-lifecycle-controls` (closes `in-app-dialogs`).
5. **S-10 export + S-9 manual editor + S-8 metadata/resources** — this is what makes the
   instructor side real; pair with `designer-visual-topology-builder` since it's the same dialog.
6. `windows-desktop-import-lab-file` (+ S-14 identity, S-15 samples, decide C1/C8).
7. **S-11 open shell** and `windows-desktop-embedded-lab-view` (the two "use the lab" stories).
8. `runtime-image-pull-progress` split: async start first, pull progress second (+ S-17).
9. **S-2 API supervision + S-3 packaging** — can run in parallel with 3–8 by a second stream;
   must land before any real student trial.
10. Quality tail: S-16, S-18, S-19, S-20, S-21.

---

## 7. Quick wins that need no new story (do during the next touch)

- Add the 6 missing ACs from §2.1 to the JSON.
- Fix `latest_checkpoint` wording for `in-app-dialogs`.
- Change `runtime-host-port-availability` last AC to "start" only and close it (after Q-2).
- Add "edit" to `designer-visual-topology-builder` ACs.
- Remove `.zip` from `import-lab-file` unless S-13 is accepted.
- Add the HTTPS/self-signed-cert edge case to `embedded-lab-view`.
- Add the "Draft/Ready/Error" status mapping table to `labs-dashboard`.
- Delete the stale "Suggested MVP Backlog" list from `user-stories.md` (or mark it historical)
  and add the 9 untracked stories to the phase narrative.
