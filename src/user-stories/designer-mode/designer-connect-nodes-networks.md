# Connect Nodes to Networks

## User Story

As an instructor,  
I want to attach node interfaces to networks with IP addresses,  
so that I can design realistic network topologies.

## Why This Matters

Interfaces turn independent nodes and networks into a runnable topology. This is where the lab begins to represent actual networking scenarios.

## User Flow

1. The instructor selects a node.
2. The instructor chooses a network to attach.
3. The instructor assigns an interface address.
4. The app validates the address against the selected network.
5. The topology view updates to show the connection.

## Functional Requirements

- The instructor can create, edit, and remove interfaces.
- Interfaces reference existing nodes and networks.
- Interface addresses belong to the selected network.
- A node cannot have more than one interface on the same network.
- IP addresses cannot be assigned more than once.

## Acceptance Criteria

- The instructor can select a node and network.
- The instructor can assign an IP interface address.
- The address must belong to the selected network.
- A node cannot have duplicate interfaces on the same network.
- Duplicate IP assignments are rejected.

## Edge Cases

- The selected node or network is renamed.
- The selected network subnet changes and makes the address invalid.
- The instructor attempts to assign a network address or broadcast address.

## Implementation Notes

- The current API validates unknown references, out-of-network addresses, duplicate attachments, and duplicate IPs.
- Consider helper UI for suggesting the next available IP address.
