# Define Docker Resource Requirements

## User Story

As an instructor,  
I want to define required container resources,  
so that student machines allocate predictable virtual lab environments.

## Why This Matters

Labs should be predictable and respectful of student hardware. Resource settings help instructors describe expected CPU, memory, and port needs before a student starts a lab.

## User Flow

1. The instructor edits a node.
2. The instructor selects a Docker image.
3. The instructor optionally sets CPU, memory, and port requirements.
4. The app validates the values.
5. The student sees estimated resource cost before starting the lab.

## Functional Requirements

- Each node must define a Docker image.
- Each node may define CPU limits.
- Each node may define memory limits.
- Each node may define exposed or published ports.
- The API rejects invalid resource values.
- The desktop app summarizes total lab resource requirements.

## Acceptance Criteria

- Each node can specify a Docker image.
- Each node can optionally specify CPU limits.
- Each node can optionally specify memory limits.
- Each node can optionally specify exposed ports.
- The app validates invalid or missing resource values.

## Example

```json
{
  "id": "router",
  "image": "alpine:3.21",
  "resources": {
    "cpu": 1,
    "memory_mb": 512
  }
}
```

## Edge Cases

- A resource limit is valid in the spec but unsupported by the local Docker backend.
- A lab requires more memory than the host appears to have available.
- Two nodes request the same host port.
- An image is private or unavailable.

## Implementation Notes

- The current `Node` model already requires `image`.
- Resource fields should be optional at first.
- Runtime enforcement may vary by Docker platform.

## Update 2026-10-24

`resources` gained `sysctls` (a map of namespaced kernel parameters, `net.*` / `kernel.*` / `fs.*`), passed to Docker as `--sysctl k=v` without privileged mode. Its first use is the designer's Router preset (`net.ipv4.ip_forward=1`). Schema stays 1.x (additive, optional).
