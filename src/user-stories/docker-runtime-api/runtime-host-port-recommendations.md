# Host Port Recommendations

## User Story

As a lab designer or student,  
I want Practicum to recommend available host ports,  
so that I can quickly fix port conflicts without guessing.

## Why This Matters

Students and instructors should not have to know which ports are free on their machine. If a preferred port is unavailable, Practicum should offer safe alternatives.

## User Flow

1. The user enters or imports a lab with conflicting host ports.
2. Practicum identifies unavailable ports.
3. Practicum suggests one or more available replacements.
4. The user accepts a recommendation or chooses another port.
5. The lab spec updates before validation/export/start.

## Functional Requirements

- Practicum can suggest available TCP ports.
- Practicum can suggest available UDP ports when needed.
- Recommendations avoid the Practicum API port.
- Recommendations avoid ports already used in the current lab spec.
- Recommendations prefer nearby or conventional alternatives when possible.

## Acceptance Criteria

- A conflicting host port includes at least one recommended replacement.
- Recommended ports are currently available.
- Recommended ports do not conflict with other mappings in the same lab.
- The UI can apply a recommended port to the affected mapping.

## Edge Cases

- No nearby ports are available.
- Recommended ports become unavailable before start.
- The lab has multiple conflicting ports.
- The user wants to reserve a specific port anyway.

## Implementation Notes

- The backend could expose an endpoint such as `POST /ports/check` or include recommendations in lab validation errors.
- The desktop app should present recommendations inline next to the affected port field.
