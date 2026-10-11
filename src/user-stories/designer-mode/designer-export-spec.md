# Export Lab Spec

## User Story

As an instructor,  
I want to export a completed lab spec file,  
so that I can distribute it to students.

## Why This Matters

Export is the bridge between Designer Mode and Student Import Mode. The exported file should be portable, validated, and complete enough to run the lab elsewhere.

## User Flow

1. The instructor clicks Export.
2. The app validates the current lab.
3. The app asks where to save the file.
4. The app writes a portable spec file.
5. The instructor distributes the file to students.

## Functional Requirements

- Export includes topology data.
- Export includes lab metadata.
- Export includes manual content.
- Export validates before writing or clearly warns if invalid.
- The exported file is importable by another Practicum installation.

## Acceptance Criteria

- The app exports a portable JSON spec file.
- The exported file includes topology and manual content.
- The exported file can be imported on another machine.
- The export process validates the spec before completion.

## Edge Cases

- The destination file already exists.
- The export path is not writable.
- The lab references images that students may not be able to access.
- The app version exports a newer schema than a student can import.

## Implementation Notes

- JSON is already the natural format for the current API.
- Consider including a top-level schema version to support future migrations.
