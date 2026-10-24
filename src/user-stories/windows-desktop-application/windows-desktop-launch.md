# Launch Desktop Application

## User Story

As a learner or instructor,  
I want to open Practicum as a Windows desktop application,  
so that I can manage labs without using the command line.

## Why This Matters

The application should feel approachable to students who may not be comfortable with terminals, Docker commands, or API tooling. This story establishes the app shell, startup experience, and readiness checks that later workflows depend on.

## User Flow

1. The user launches Practicum from Windows.
2. The app opens to the main workspace.
3. The app checks whether the local Practicum API is reachable.
4. The app checks whether Docker is available.
5. The app shows ready, degraded, or blocked status.

## Functional Requirements

- The application starts from Windows.
- Startup checks run without freezing the UI.
- API availability and Docker availability are shown separately.
- The app distinguishes between "API unavailable" and "Docker unavailable".
- The app provides a next action when something is missing.

## Acceptance Criteria

- The app launches on Windows.
- The app shows whether the local Practicum API is reachable.
- The app shows whether Docker is available.
- If either dependency is unavailable, the app displays a useful error state.

## Edge Cases

- Docker Desktop is installed but not running.
- Docker is running but the current user cannot access it.
- The local API is not running.
- The local API is running on a non-default port.

## Implementation Notes

- Treat this as the foundation for the desktop shell.
- Startup checks should be refreshable from the UI.
- Errors should be actionable and written for students.

## Implementation Status (update 2026-10-24)

The startup health check now retries timeouts with longer waits (3 s, 6 s, 10 s) before reporting Blocked, and a timed-out API is worded as "not answering in time … wait a moment and select Retry" rather than "start the API" (Tigre/06 #11). The readiness information lives in the title bar's status chip and a collapsible connection panel (API line, Docker line, next action, API base URL + Retry), opened automatically when Blocked.
