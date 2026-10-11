# Create Extension Points

## User Story

As an advanced user or institution,  
I want Practicum to support extensions,  
so that the platform can grow without bloating the open-source core.

## Future Ideas

- Runtime providers beyond local Docker
- Custom validation plugins
- Manual renderers
- Assessment checkers
- Import/export adapters
- Institution policy plugins

## Acceptance Criteria

- Core code exposes stable extension boundaries.
- Extensions cannot break basic local lab behavior.
- Open-source and paid extensions use the same public integration patterns where possible.

## Paywall Guidance

The extension system itself should be open source. Specific hosted, enterprise, or commercial extensions can be paid.
