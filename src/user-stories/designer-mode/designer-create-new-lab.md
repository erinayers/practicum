# Create a New Lab

## User Story

As an instructor,  
I want to create a new lab from scratch,  
so that I can design a reusable learning environment.

## Why This Matters

This is the entry point for instructors. It should help them create a valid starting lab without requiring them to understand the raw JSON format.

## User Flow

1. The instructor opens Designer Mode.
2. The instructor chooses to create a new lab.
3. The app creates a blank draft.
4. The instructor enters basic metadata.
5. The instructor adds topology pieces and manual content over time.
6. The instructor saves the draft locally.

## Functional Requirements

- Designer Mode supports a new blank lab draft.
- The draft tracks unsaved changes.
- The instructor can name the lab.
- The instructor can add nodes and networks.
- The instructor can save locally before export.

## Acceptance Criteria

- The instructor can create a blank lab.
- The instructor can name the lab.
- The instructor can add at least one node.
- The instructor can add at least one network.
- The instructor can save the lab locally.

## Edge Cases

- The instructor closes the app with unsaved changes.
- The instructor creates a lab with only metadata and no topology.
- Local save fails due to file permissions.

## Implementation Notes

- A draft can be invalid while the instructor is still editing.
- Validation should be available throughout, but export should require a valid spec.
