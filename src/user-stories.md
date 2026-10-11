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

Phases 1-6 built a working API and a functional, form-based desktop shell. Clickable mockups then revealed where the desktop UI hasn't caught up to already-"done" backend capability, plus a few net-new UX requirements surfaced during that review. This phase closes that gap before any further API work.

22. [In-App Dialogs Only](user-stories/windows-desktop-application/windows-desktop-in-app-dialogs.md)
23. [Labs Dashboard](user-stories/windows-desktop-application/windows-desktop-labs-dashboard.md)
24. [Pre-Start Readiness Gate](user-stories/windows-desktop-application/windows-desktop-prestart-lab-gate.md)
25. [Import Lab File and Launch](user-stories/windows-desktop-application/windows-desktop-import-lab-file.md)
26. [Lab Lifecycle Controls](user-stories/windows-desktop-application/windows-desktop-lab-lifecycle-controls.md)
27. [Embedded Lab View](user-stories/windows-desktop-application/windows-desktop-embedded-lab-view.md)
28. [Visual Topology Builder (Basic)](user-stories/designer-mode/designer-visual-topology-builder.md)

## First Product Slice

The first complete slice should let an instructor create or export a JSON lab file, let a student import it into the Windows app, validate it, start Docker containers, open the lab manual flyout, and stop the lab when finished.
