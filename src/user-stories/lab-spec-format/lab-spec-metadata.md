# Define Lab Metadata

## User Story

As an instructor,  
I want to define basic lab metadata,  
so that students understand the lab's purpose before running it.

## Why This Matters

Students need context before starting a lab, and instructors need a way to identify, version, and distribute lab files. Metadata also helps the app display useful lab cards, import summaries, and compatibility warnings.

## User Flow

1. The instructor creates or edits a lab.
2. The instructor enters a name, description, author, and version.
3. The app validates required metadata.
4. The metadata appears in previews, exports, and imported lab lists.

## Functional Requirements

- A lab must have a human-readable name.
- A lab may include a description.
- A lab may include an author or instructor field.
- A lab may include a version.
- Metadata is included in exported specs.
- Metadata is visible during student import preview.

## Acceptance Criteria

- A lab spec includes a name.
- A lab spec can include a description.
- A lab spec can include author or instructor information.
- A lab spec can include version information.

## Edge Cases

- Lab name is empty.
- Lab name is too long for compact UI surfaces.
- Version is omitted.
- Imported specs use an older metadata shape.

## Implementation Notes

- The current model already supports `name`.
- Add optional fields carefully so existing example specs remain valid.
- Consider a top-level `schema_version` separate from lab version.
