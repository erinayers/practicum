# Add Nodes to a Lab

## User Story

As an instructor,  
I want to add Docker-backed nodes to my lab topology,  
so that students can interact with simulated hosts, routers, or services.

## Why This Matters

Nodes are the core units students will interact with. They represent hosts, routers, clients, servers, and other containers inside the lab.

## User Flow

1. The instructor opens the node editor.
2. The instructor adds a node.
3. The instructor enters an ID and Docker image.
4. The app validates the ID and required image.
5. The node appears in the topology and node list.

## Functional Requirements

- The instructor can add, edit, and remove nodes.
- Each node has a unique ID.
- Each node has a Docker image.
- Node IDs match backend validation rules.
- Validation errors appear close to the relevant field.

## Acceptance Criteria

- The instructor can add a node with an ID.
- The instructor can choose or type a Docker image.
- Node IDs must match the API validation rules.
- Duplicate node IDs are rejected.
- Invalid nodes show clear validation messages.

## Edge Cases

- The instructor renames a node already referenced by interfaces.
- The instructor removes a node attached to one or more networks.
- The instructor enters an image that cannot be pulled.

## Implementation Notes

- The current API supports node IDs and images.
- Designer UI should keep references intact when possible or clearly explain what will be removed.
