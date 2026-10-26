# Choose and Configure the Local Data Directory

As a user of the installed Practicum app, I want its database stored in a stable per-user data location so that upgrades do not remove my labs and the app does not need administrator access.

## Acceptance criteria

- Packaged Windows use stores the SQLite database under the current user's local application data directory (for example, `%LOCALAPPDATA%\\Practicum`).
- Development use has a documented default and supports an environment-variable override for the database path.
- The parent directory is created when needed, and path resolution works when launched from a different working directory.
- The selected path is visible in startup diagnostics without exposing unrelated environment data.
- Documentation explains how to locate, copy, and back up the database file, and clarifies that lab JSON export remains the portable sharing format.
- Tests cover default, override, and directory creation behavior.

## Notes

Do not put mutable user data in the install directory or inside Docker. The data-directory choice can be revisited if Practicum gains multi-user hosted operation.
