# Import probes — manual test files for "Import Existing Lab"

Each file exercises one path of the desktop import flow
(`windows-desktop-import-lab-file`). Start Practicum (`start-practicum.bat`), click
**Import Existing Lab** (welcome screen or dashboard), then **Browse computer…** and pick a file from this folder.
For `.zip` you need to switch the picker's filter to *All files*.

| File | What it is | Expected outcome |
|---|---|---|
| `1-valid-auto-start.json` | Two `alpine:3.21` hosts on `10.93.1.0/24`, no host ports, a 3-task manual | Progress runs *Reading → Importing → Checking host ports and networks → Starting containers* (with the real per-node progress — "Downloading alpine:3.21 · 40% · 2 of 5 layers (host-a)" on a first pull), then the dialog closes by itself and the **running view** opens for **Import Probe – Two Hosts**: badge *Running*, the instructions flyout on the right, and the **Lab nodes** table listing `host-a` / `host-b` as *running* with an **Open shell** button each. Click it: a new console window opens *inside* the node (`/ #` prompt); `ping -c 3 10.93.1.20` should get replies. (First run pulls `alpine` — a few seconds.) If Docker Desktop is not running, the dialog stays open with "❌ … was imported but could not be started: …" and the lab is still in the list. |
| `2-port-conflict-gate.json` | nginx mapping **host port 8000** — the port the Practicum API itself uses | Never auto-starts. The dialog closes and **Review Before Starting** (the pre-start gate) opens with one conflict: `web · 8000/tcp · Reserved by the Practicum API` and a **Use <port>** button. Click it → conflict clears → **Start Lab** enables. Cancel instead → the dashboard shows the lab's card as *Ready* with a note "… imported. Use Start on its card when ready." |
| `3-unsupported-schema-version.json` | Same as file 1 with `"schema_version": "2.0"` | "Import did not complete" with one error: `schema_version: schema_version '2.0' is not supported by this version of Practicum (supported: 1.x)`. Nothing is added to the dashboard. **Choose another file** is offered. |
| `4-schema-errors.json` | Missing `image`, uppercase node id, unknown field `difficulty` (also an out-of-subnet address, which is only reported once the field errors are fixed) | Three bullet errors: `nodes[0].image: Field required`, `nodes[1].id: String should match pattern …`, `difficulty: Extra inputs are not permitted`. Nothing added. |
| `5-malformed.json` | Truncated JSON | Caught before any API call: `'5-malformed.json' is not valid JSON: Expecting ',' delimiter (line 6, column 1).` |
| `6-not-a-lab-object.json` | A JSON list | `… contains a list, not a lab definition. A lab file is a single JSON object with 'name', 'nodes', 'networks' and 'interfaces'.` |
| `7-bundle-not-supported.zip` | A zip containing a valid `lab.json` | `… is a lab bundle (.zip). Bundles aren't supported yet — choose the .json lab export instead.` |

> **Subnet already in use** (e.g. importing `ubuntu-quickstart.json` when an old Quick Start
> network still exists): since 2026-10-23 this no longer fails at start. The import stops at the
> pre-start gate, whose **Network Conflicts** section names the owner — "Left over from an earlier
> session: 'practicum-…-lab-net' (10.50.0.0/24, 1 container)" or "Used by lab '…'" — and offers
> **Remove leftover** / **Reset '<lab>'** / **Use 10.90.0.0/24**. Pick one, then **Start Lab**.
> To reproduce on purpose: import `ubuntu-quickstart.json` (one of the bundled samples) twice and
> start both. The probe labs use `10.93.x.0/24` to stay clear of the Quick Start subnet.

> **"100 % packet loss" between the two hosts?** Check the **Address** column of the Lab nodes
> table first: if the pre-start gate moved the lab to a free subnet (a leftover `10.93.1.0/24`
> network from an earlier run), the hosts are now on `10.90.x.x`. Since 2026-10-24 the manual's
> addresses are rewritten along with the move, so the text and the table should agree; if they
> don't, the table is right.

> **Don't ssh/ping node addresses from Windows.** `10.93.1.x` only exists inside Docker Desktop's
> VM; Windows can reach a node only through a *published* port (like the webtop sample's 3000),
> and the probe nodes run no SSH server anyway. **Open shell** is the way in.

Also worth checking while you're there:

- **Recent list** — after a successful import, reopen *Import Existing Lab*: the file is at the top
  as "Recent · N KB", above the three bundled samples. Rename/move it and reopen: the row is
  greyed "Recent · file not found". The list survives restarting the app.
- **Double-click** a row = Open. Cancel/Escape/✕ do nothing while a stage is in progress.
- **API down** — stop the API window, click *Import Existing Lab*: an amber banner says the API is
  not available and *Browse*/*Open* are disabled (no generic error).
- **Importing file 1 twice** creates a second lab with the same name (current behaviour, Tigre/09
  Q-1 is still open).
