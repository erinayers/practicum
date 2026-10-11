# Connect to Local API

## User Story

As the desktop application,  
I want to communicate with the local Practicum API,  
so that lab validation and lab management happen through the backend service.

## Why This Matters

The desktop app should be a client of the local API, not a second implementation of lab logic. This keeps validation, lab state, Docker orchestration, and future automation in one backend layer.

## User Flow

1. The app starts and reads the configured API base URL.
2. The app calls `GET /health`.
3. If healthy, the app loads locally defined labs with `GET /labs`.
4. If unavailable, the app shows a disconnected state.
5. The user can retry or update the API base URL.

## Functional Requirements

- The app defaults to `http://127.0.0.1:8000`.
- The API base URL can be configured.
- The app calls `GET /health` on startup.
- The app calls `GET /labs` after a successful health check.
- API requests handle timeouts, connection failures, and non-200 responses.

## Acceptance Criteria

- The app calls `GET /health` on startup.
- The app handles unavailable API responses gracefully.
- The API base URL can be configured or defaults to `http://127.0.0.1:8000`.
- The app can list locally defined labs using `GET /labs`.

## Edge Cases

- API returns malformed JSON.
- API returns a version the client does not understand.
- API is reachable but unhealthy.
- API starts after the desktop app has already opened.

## Implementation Notes

- The current API already exposes `GET /health` and `GET /labs`.
- Consider adding an API version field to `GET /health` later.
- Keep API client code isolated and reusable.
