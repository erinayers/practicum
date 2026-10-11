# Add Networks to a Lab

## User Story

As an instructor,  
I want to define virtual networks and subnets,  
so that lab nodes can communicate in a controlled topology.

## Why This Matters

Networks define the boundaries and communication paths of the lab. In networking labs especially, subnets are part of the learning objective.

## User Flow

1. The instructor adds a network.
2. The instructor enters a network ID.
3. The instructor enters an IPv4 subnet.
4. The app validates the CIDR value.
5. The network becomes available for node interfaces.

## Functional Requirements

- The instructor can add, edit, and remove networks.
- Each network has a unique ID.
- Each network defines a valid IPv4 subnet.
- The UI shows which nodes are attached to a network.
- Removing a network handles existing interfaces deliberately.

## Acceptance Criteria

- The instructor can add a network with an ID.
- The instructor can define an IPv4 subnet.
- Duplicate network IDs are rejected.
- Invalid CIDR ranges are rejected.
- The UI shows which nodes are attached to each network.

## Edge Cases

- The instructor changes a subnet after interfaces have assigned addresses.
- Two networks use overlapping subnets.
- A network is deleted while nodes are attached.

## Implementation Notes

- Current backend validation supports unique IDs and IPv4 network parsing.
- Overlapping subnet validation is not currently required but may become useful.
