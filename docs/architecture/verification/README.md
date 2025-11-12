# Controller Verification Module

This module is responsible for ensuring that only **trusted and authorized controllers** can join and participate in the PDSNO network.  
It defines how controllers (Global, Regional, and Local) authenticate and validate themselves through a secure, multi-step process managed primarily by the **Primary Global Controller**.


## Purpose
To prevent unauthorized or rogue controllers from joining the orchestration network and to maintain system-wide trust.


## Core Responsibilities
- Validate incoming controller registration requests.
- Perform cryptographic **token and signature checks**.
- Manage **policy-based authorization** of controllers.
- Assign unique and verifiable controller identities upon successful validation.



## Related Documentation
Detailed design and pseudocode can be found here:

 [**Controller Verification System**](../../docs/controller_verification.md)



## Current Status
| Stage | Description |
|-------|--------------|
| 🟢 Design | Core logic and flow finalized |
| 🟡 Development | Initial implementation planned |
| ⚪ Testing | Pending future iterations |


## Notes for Contributors
- Follow the `AlgorithmBase` interface structure (`initialize`, `execute`, `finalize`) for consistency.
- Avoid hardcoding controller names or IDs — they will be dynamically assigned during validation.
- Validation metadata should be loaded from `context.yaml` at runtime.


**Maintainer:** Alexander Finch  
**Component:** Controller Verification  
**Status:** Design Ready
