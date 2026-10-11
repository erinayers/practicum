# Validate Lab Design

## User Story

As an instructor,  
I want to validate my lab before exporting it,  
so that students receive a working spec file.

## Why This Matters

Validation protects students from broken lab files and gives instructors feedback before distribution. It should be fast, local, and visible throughout the design process.

## User Flow

1. The instructor clicks Validate or reaches export.
2. The app sends the current lab definition to `POST /labs/validate`.
3. The API returns success or validation errors.
4. The app highlights fields that need attention.
5. The instructor fixes issues and validates again.

## Functional Requirements

- The app calls the backend validation endpoint.
- Validation results are shown in the designer.
- Errors identify the affected topology element when possible.
- Export requires or triggers validation.
- API validation errors and connection failures are handled differently.

## Acceptance Criteria

- The app sends the lab definition to `POST /labs/validate`.
- Validation success is clearly shown.
- Validation errors identify the affected node, network, or interface.
- Export is disabled or discouraged when validation fails.

## Edge Cases

- The API is unavailable during validation.
- The lab is valid structurally but not runnable on the local machine.
- The user edits the lab after the last successful validation.

## Implementation Notes

- Current API validation exists.
- The API currently returns standard FastAPI validation errors; later work may add friendlier structured error codes.
