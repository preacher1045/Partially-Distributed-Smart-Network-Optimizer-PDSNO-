---
title: Controller Verification System
description: Design and flow of the controller validation system within PDSNO.
author: Alexander Adjei
status: Draft Complete
last_updated: 2025-11-11
component: Controller Verification Module
---

# Controller Verification System (PDSNO)

## Overview

The Controller Verification System ensures that only authorized and trusted controllers (Global, Regional, and Local) participate in the PDSNO network.  
This process prevents malicious or rogue controllers from joining and helps maintain network integrity, trust, and consistency across all controller layers.



## Purpose

The verification process acts as a **security and trust establishment phase** between controllers.  
Before a controller (e.g., Regional or Local) is accepted into the system, it must be validated and approved by the higher-level controller — primarily the **Primary Global Controller (`global_cntl_1`)**.



## Key Concepts

### 1. Hierarchical Control

- **Primary Global Controller (`global_cntl_1`)**  
  Highest authority responsible for validating other controllers and assigning roles.

- **Secondary Global Controller (`global_cntl_2`)**  
  Backup or subordinate global controller that receives roles from the primary global controller.

- **Regional Controllers**  
  Receive validation and naming rights from the global controllers, but must be validated before full registration.

- **Local Controllers**  
  Operate closest to the network devices and must be validated through their respective regional controllers.



## Validation Flow Summary

When a lower-level controller requests validation:

1. The controller generates a **validation request** containing metadata, temporary ID, timestamp, and a **bootstrap token**.  
2. The request is sent to the higher controller (usually the Primary Global Controller).  
3. The higher controller validates the request using a structured multi-step process.
4. Then it assigns a name, role and privilages.



## Verification Logic

### 1. Request Reception
The Global Controller receives a validation request from a lower controller (Regional or Local) that includes:
- `temp_id`
- `timestamp`
- `bootstrap_token`
- `metadata` (e.g., controller type, network region, etc.)

### 2. Timestamp and Blocklist Check
- The system checks if the `timestamp` is **fresh** (same day or within defined freshness window).  
- The system checks whether the `temp_id` exists in a **blocklist** of rejected or malicious controllers.  
- If timestamp is stale or temp_id is blocked → **Reject immediately.**

### 3. Bootstrap Token Validation
- If checks pass, the Global Controller verifies the `bootstrap_token` via shared secret or cryptographic signature.  
- If verification fails → **Reject and flag for audit.**

### 4. Challenge–Response Verification
- Upon successful token verification, the Global Controller issues a **challenge** containing:
  - The `temp_id`
  - A cryptographically secure **nonce**
- The requesting controller signs this challenge and returns it.
- The Global Controller verifies the **signature**:
  - If invalid → **Reject**
  - If valid → proceed to policy verification

### 5. Policy and Metadata Verification
- Cross-checks metadata against defined **policy configurations**.  
  - Ensures regional controllers are in permitted zones.  
  - Ensures local controllers belong to the correct regional zones.  
- If mismatch → **Flag for manual review or reject.**

### 6. Identity Assignment
- Once all validations pass, a **unique controller identity** is assigned:
global_cntl_1 → validates regional_cntl_3 → assigns ID → regional_cntl_3@zoneA

## Pseudocode

```python
function validate_registration(req):
    if not fresh(req.timestamp) or blacklisted(req.temp_id):
        return reject("invalid request")

    if has_bootstrap_token(req.proof):
        accept_shortpath = verify_token(req.proof)
        if accept_shortpath:
            goto assign_identity

    send_challenge(req.temp_id, nonce)
    reply = await signed_nonce(timeout=CHALLENGE_TIMEOUT)
    if not verify_signature(reply.signature, req.pubkey, nonce):
        return reject("signature invalid")

    if not policy_checks(req.metadata):
        return reject("policy mismatch")

assign_identity:
    assigned_id = allocate_id(req.type, req.region)
    cert = sign_certificate(assigned_id, req.pubkey, role, expiry)
    save_context(assigned_id, req.metadata, validator=this_global)
    write_audit("validation", assigned_id, req.temp_id, timestamp)
    return approve_response(assigned_id, cert)

```
## Security Considerations
- Timestamp Freshness – Prevents replay attacks or delayed requests.
- Blocklist Enforcement – Blocks malicious or previously rejected controllers.
- Bootstrap Token – Acts as a one-time trust seed.
- Challenge–Response Authentication – Confirms controller identity ownership.
- Policy Cross-Validation – Ensures correct role and region assignment.
- Identity Uniqueness – Each verified controller has a distinct ID.

## Future Enhancements
- Distributed Validation Ledger
Record validation history in a distributed or blockchain-like system.

- Dynamic Role Adjustment
Allow promotion/demotion of controllers based on trust or performance metrics.

## Key Rotation
Regular renewal of bootstrap and validation keys to enhance long-term security.