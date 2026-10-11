# Preview Imported Lab

## User Story

As a student,  
I want to preview the lab topology and manual before starting,  
so that I understand what will run on my computer.

## Why This Matters

Students should know what containers, images, networks, and resources will be used before the app changes their Docker environment.

## User Flow

1. The student selects an imported lab.
2. The app displays lab metadata.
3. The app shows Docker images and estimated resources.
4. The app shows a read-only topology.
5. The app makes the lab manual available.

## Functional Requirements

- The preview shows lab name and description.
- The preview shows required Docker images.
- The preview summarizes estimated CPU and memory needs when available.
- The preview shows topology without allowing student edits.
- The manual flyout is accessible from preview or lab view.

## Acceptance Criteria

- The app shows the lab name and description.
- The app shows required Docker images.
- The app shows estimated resource requirements.
- The app shows the topology in read-only mode.
- The app shows the lab manual flyout.

## Edge Cases

- Resource requirements are missing from the spec.
- The topology is too large for a compact view.
- The manual is missing or empty.
- Required images are not present locally.

## Implementation Notes

- The preview can be text/table-based at first.
- A visual topology can come later after the data model stabilizes.
