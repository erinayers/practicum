# Reset Lab

## User Story

As a student,  
I want to reset a lab,  
so that I can return to the original instructor-provided state.

## Why This Matters

Labs are learning spaces, and students will make mistakes. Reset gives them a clean recovery path without needing to re-import the lab.

## User Flow

1. The student chooses Reset for an imported lab.
2. The app warns that runtime changes will be removed.
3. The student confirms.
4. The runtime removes existing containers and lab-created resources.
5. The original imported spec remains available.

## Functional Requirements

- Reset requires confirmation.
- Reset stops and removes lab containers.
- Reset cleans up lab-created resources according to runtime rules.
- Reset preserves the original imported spec.
- Reset does not modify instructor-authored manual content.

## Acceptance Criteria

- The app stops and removes existing lab containers.
- The original spec remains available.
- The student can start the lab again from a clean state.
- The app warns before destructive reset actions.

## Edge Cases

- Reset partially fails.
- Docker resources were manually changed outside Practicum.
- The student has local progress data.
- The lab is already stopped.

## Implementation Notes

- Reset is more destructive than Stop and should be visually distinct.
- Progress reset should be a separate option.
