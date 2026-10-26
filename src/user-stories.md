# Practicum User Stories

Practicum is a Windows desktop application for designing, importing, and running reproducible Docker-based lab environments locally. Instructors author lab specifications and lab manuals, while students import those specifications and run the lab on their own computer through a local API.

## Product Vision

Practicum helps instructors create portable technical labs and helps students run those labs consistently on Windows machines using Docker.

The application has two primary modes:

- **Designer Mode**: instructors create lab specs, define topology, author the lab manual, validate the lab, and export it.
- **Import Mode**: students import instructor-authored specs, preview the lab, start or stop the local Docker environment, and follow the lab manual.

The Windows application communicates with the local Practicum API, which is responsible for validation, lab state, and Docker orchestration.

## Personas

### Instructor / Lab Designer

An instructor creates reusable lab environments for students. They define the lab topology, required Docker images, resource needs, and instructional content.

### Student / Learner

A student imports a lab file provided by an instructor, starts the local lab environment, follows the embedded manual, and stops or resets the lab when needed.

### Local Runtime

The local runtime is the API and Docker orchestration layer. It validates specs, creates containers and networks, tracks status, and reports errors to the desktop app.

## Epic Folders

- [Windows Desktop Application](user-stories/windows-desktop-application/README.md)
- [Lab Spec Format](user-stories/lab-spec-format/README.md)
- [Designer Mode](user-stories/designer-mode/README.md)
- [Student Import Mode](user-stories/student-import-mode/README.md)
- [Lab Manual Flyout](user-stories/lab-manual-flyout/README.md)
- [Docker Runtime API](user-stories/docker-runtime-api/README.md)

## Suggested MVP Backlog

1. Extend the lab spec model with manual content and optional resource settings.
2. Add import and export support for spec files.
3. Add API runtime endpoints for start, stop, and status.
4. Implement Docker runtime behind the API.
5. Build the Windows app shell with local API health checks.
6. Add Student Import Mode.
7. Add Designer Mode with form-based topology editing.
8. Add visual topology designer after the data model feels stable.
9. Add manual flyout.
10. Add progress tracking and richer student workflow features.

## Recommended Story Order

This order builds the product from the inside out: first the lab file contract, then validation and import/export, then runtime orchestration, then the Windows workflows that sit on top of it.

### Phase 1: Strengthen the Lab Spec

1. [Define Lab Metadata](user-stories/lab-spec-format/lab-spec-metadata.md)
2. [Define Docker Resource Requirements](user-stories/lab-spec-format/lab-spec-docker-resources.md)
3. [Author Lab Manual](user-stories/designer-mode/designer-author-manual.md)

### Phase 2: Validate and Move Lab Files Around

4. [Validate Lab Design](user-stories/designer-mode/designer-validate-lab.md)
5. [Export Lab Spec](user-stories/designer-mode/designer-export-spec.md)
6. [Import Instructor Spec](user-stories/student-import-mode/student-import-spec.md)
7. [Preview Imported Lab](user-stories/student-import-mode/student-preview-imported-lab.md)

### Phase 3: Add Runtime API and Docker Control

8. [Start Lab Through API](user-stories/docker-runtime-api/runtime-api-start-lab.md)
9. [Stop Lab Through API](user-stories/docker-runtime-api/runtime-api-stop-lab.md)
10. [Report Lab Runtime Status](user-stories/docker-runtime-api/runtime-api-status.md)
11. [Start Lab](user-stories/student-import-mode/student-start-lab.md)
12. [Stop Lab](user-stories/student-import-mode/student-stop-lab.md)
13. [Reset Lab](user-stories/student-import-mode/student-reset-lab.md)

### Phase 4: Build the Windows Application Shell

14. [Launch Desktop Application](user-stories/windows-desktop-application/windows-desktop-launch.md)
15. [Connect to Local API](user-stories/windows-desktop-application/windows-desktop-local-api.md)

### Phase 5: Build Basic Designer Workflows

16. [Create a New Lab](user-stories/designer-mode/designer-create-new-lab.md)
17. [Add Nodes to a Lab](user-stories/designer-mode/designer-add-nodes.md)
18. [Add Networks to a Lab](user-stories/designer-mode/designer-add-networks.md)
19. [Connect Nodes to Networks](user-stories/designer-mode/designer-connect-nodes-networks.md)

### Phase 6: Improve the Student Learning Experience

20. [View Lab Manual While Working](user-stories/lab-manual-flyout/manual-view-flyout.md)
21. [Track Manual Progress](user-stories/lab-manual-flyout/manual-track-progress.md)

### Phase 7: Close the Desktop UI Gap (mockup-driven)

Phases 1-6 built a working API and a functional, form-based desktop shell. Clickable mockups then revealed where the desktop UI hasn't caught up to already-"done" backend capability, plus a few net-new UX requirements surfaced during that review. This phase closes that gap. Nearly all of it is desktop UI only — the one exception is story 29, a real backend gap the mockup review surfaced (today's start sequence has no incremental progress to show, so the mockups fake it with a timer).

22. [In-App Dialogs Only](user-stories/windows-desktop-application/windows-desktop-in-app-dialogs.md)
23. [Labs Dashboard](user-stories/windows-desktop-application/windows-desktop-labs-dashboard.md)
24. [Pre-Start Readiness Gate](user-stories/windows-desktop-application/windows-desktop-prestart-lab-gate.md)
25. [Import Lab File and Launch](user-stories/windows-desktop-application/windows-desktop-import-lab-file.md)
26. [Lab Lifecycle Controls](user-stories/windows-desktop-application/windows-desktop-lab-lifecycle-controls.md)
27. [Embedded Lab View](user-stories/windows-desktop-application/windows-desktop-embedded-lab-view.md)
28. [Visual Topology Builder (Basic)](user-stories/designer-mode/designer-visual-topology-builder.md)
29. [Image Pull and Start Progress](user-stories/docker-runtime-api/runtime-image-pull-progress.md) (backend)

Stories added during Phase 7 as the work surfaced them (2026-10-23/24): backend enablers the desktop stories turned out to need, and mockup screens that had no story.

30. [Subnet Conflict Detection and Resolution](user-stories/docker-runtime-api/runtime-subnet-conflicts.md) (backend + gate)
31. [Open a Shell on a Lab Node](user-stories/windows-desktop-application/windows-desktop-open-node-shell.md)
32. [Restart a Lab and Start After Stop](user-stories/docker-runtime-api/runtime-lab-restart.md) (backend enabler for 26)
33. [Delete a Lab Through the API](user-stories/docker-runtime-api/runtime-delete-lab.md) (backend enabler for 23)
34. [Lab Origin and Activity Timestamps](user-stories/lab-spec-format/lab-origin-and-timestamps.md) (backend enabler for 23)
35. [Desktop Visual Theme (Mockup Look and Feel)](user-stories/windows-desktop-application/windows-desktop-visual-theme.md)
36. [Create New Lab Screen](user-stories/windows-desktop-application/windows-desktop-create-lab-screen.md)
37. [Quick Start Lab from a Template](user-stories/designer-mode/designer-quick-start-lab.md)
38. [Live Status Polling in the Running View](user-stories/windows-desktop-application/windows-desktop-status-polling.md)
39. [Machine Catalogue for the Custom Lab Designer](user-stories/designer-mode/designer-node-catalog.md) (user feedback 2026-10-24)
40. [Edit an Existing Lab](user-stories/designer-mode/designer-edit-existing-lab.md) (user feedback 2026-10-24; backend `PUT /labs/{id}`)

### Phase 8: Add Windows Quick Start Support

Windows Quick Start is a separate capability from the existing Linux-container templates.
It starts with host readiness, then a PowerShell-based Windows Server Core lab, shell integration,
and an optional catalog of compatible command-line tools. Practicum must not silently switch
Docker Desktop's global engine mode. **Done 2026-10-25 (Session 6)** - built and tested offscreen
and against the live API with a fake Docker CLI; not yet run on a Windows machine with Docker
Desktop in Windows-container mode (see Tigre/05 for the verification checklist).
**Scope change, same day:** Windows containers need Windows Pro/Enterprise/Education, which the
free plan's typical student laptop (Windows Home) lacks, so these capabilities are planned to
move behind the paid tier - described, together with a macOS counterpart, in the roadmap epic
[Premium Lab Platforms](future-roadmap/premium-lab-platforms/README.md). Nothing built here
was removed.

41. [Windows Container Readiness for Quick Start](user-stories/windows-desktop-application/windows-desktop-windows-container-readiness.md)
42. [Windows Quick Start Template](user-stories/designer-mode/designer-windows-quick-start.md)
43. [Open a PowerShell Shell on a Windows Lab Node](user-stories/windows-desktop-application/windows-desktop-open-windows-shell.md)
44. [Choose Windows Tools in Quick Start](user-stories/designer-mode/designer-windows-quick-start-packages.md)
45. [Use Design Icons Across the Desktop UI](user-stories/windows-desktop-application/windows-desktop-design-icons.md)

### Phase 9: Keep Labs Across Restarts

Use an embedded SQLite database for the local app. The database file lives in a stable per-user
application-data directory in packaged use, with a configurable path for development. No separate
database server or Docker container is required. Docker remains the source of truth for runtime
state, which is reconciled when the API starts.

46. [Persist Labs in a Local SQLite Database](user-stories/backend-storage/lab-persistence-sqlite.md)
47. [Reconcile Saved Labs with Docker on Startup](user-stories/backend-storage/lab-runtime-reconciliation.md)
48. [Choose and Configure the Local Data Directory](user-stories/backend-storage/local-data-directory.md)

### Phase 10: Market and Distribute the Open-Source App

Give Practicum a public home that explains its audience and local-first workflow, helps people
install the app, and makes the open-source project easy to trust, use, and contribute to. The site
promotes the free local product and links to canonical releases; it does not imply that hosted or
paid roadmap features already exist.

49. [Explain Practicum on the Project Website](user-stories/project-website/website-product-home.md)
50. [Find and Download Practicum Releases](user-stories/project-website/website-downloads.md)
51. [Get Started and Find Help](user-stories/project-website/website-getting-started.md)
52. [Understand the Project and Contribute](user-stories/project-website/website-project-transparency.md)

## First Product Slice

The first complete slice should let an instructor create or export a JSON lab file, let a student import it into the Windows app, validate it, start Docker containers, open the lab manual flyout, and stop the lab when finished.
