# Persist Labs in a Local SQLite Database

As a Practicum user, I want labs and their local metadata to survive an API restart so that my dashboard is still there when I return.

## Acceptance criteria

- The service stores each lab definition and local bookkeeping fields (id, origin, source filename, creation/last-start timestamps, and last error) in a local SQLite database.
- Create, import, edit, delete, and port/subnet recommendation flows update the durable record consistently with their existing API behavior.
- Exported lab JSON remains portable and excludes local runtime bookkeeping fields.
- A clean database is created automatically; malformed or unsupported stored records are reported clearly and do not silently erase other valid labs.
- Start progress and other transient in-flight state remain in memory and are not treated as durable state.
- The API's existing lab routes continue to work with the persistent store, and tests cover data surviving service recreation against the same database file.

## Notes

Use Python's SQLite support through the standard library unless a concrete need for an ORM emerges. This is a local single-user store, not a separate MySQL service. Database path selection and startup Docker reconciliation are covered by companion stories.
