---
title: Communication Model
status: Active
author: Alexander Adjei
last_updated: 2026-02-14
component: Communication Layer
depends_on: PROJECT_OVERVIEW.md, docs/architecture/nib/nib_spec.md
research_basis: >
  ONF TR-521 — standardized interface naming (NBI, SBI, East/West).
  Alsheikh et al. (ARO 2024) — pub/sub recommendation over polling for state updates.
  IEEE_TNSM / DISCO — delta-sync principle for inter-controller communication.
  ONOS paper (Berde et al., 2014) — distributed data store and leader election patterns.
---

# PDSNO — Communication Model

## Overview

This document defines how PDSNO controllers communicate — which protocols are used
between which tiers, the message envelope format, how messages are authenticated,
and the retry and timeout contracts that govern reliability.

The communication model is the "nervous system" of PDSNO. The NIB is what controllers
share. The communication model is how they share it, and how they coordinate actions.

---

## Interface Summary (ONF Standard Naming)

PDSNO uses ONF TR-521 interface naming throughout:

```
External Applications / Vendor Adapters
          │
          │  NBI (Northbound Interface)
          │  REST/HTTP — request/response
          ▼
┌─────────────────────────────────────┐
│         Global Controller           │
└─────────────────────────────────────┘
          │                    │
          │  East/West         │  SBI
          │  (Validation,      │  (future — device
          │   Policy sync)     │   management)
          ▼                    ▼
┌──────────────────┐    ┌─────────────┐
│ Regional Ctrl    │◄──►│ Regional    │  East/West between peers
└──────────────────┘    └─────────────┘
          │
          │  East/West (Validation, Discovery reports)
          ▼
┌──────────────────┐
│  Local Ctrl      │
└──────────────────┘
          │
          │  SBI (NETCONF, SNMP, ICMP, ARP)
          ▼
┌──────────────────┐
│  Network Devices │
└──────────────────┘
```

---

## Protocol Assignment

Different message types have different communication requirements. Research into
distributed SDN (Alsheikh et al., 2024) confirms that publish/subscribe is
preferable over polling for state updates, while REST is appropriate for
request/response flows. PDSNO applies this split:

| Message Category | Protocol | Direction | Rationale |
|-----------------|----------|-----------|-----------|
| Controller validation | REST/HTTP | LC→RC, RC→GC | Request/response — must be synchronous, has a definite answer |
| Config approval | REST/HTTP | LC→RC, RC→GC | Request/response — approval is a decision with a result |
| Policy distribution | MQTT (pub/sub) | GC→RC→LC | Broadcast — one publisher, many subscribers, fire-and-forget with QoS |
| Discovery reports | REST/HTTP | LC→RC | Structured report — RC needs to validate and respond |
| State change events | MQTT (pub/sub) | Any→Any | Event notification — controllers subscribe to events they care about |
| NIB sync notifications | MQTT (pub/sub) | RC→LC | Push updates when NIB data changes that affect a controller's scope |
| NBI (external access) | REST/HTTP | External→GC | Standard API — external tools expect REST |
| SBI (device management) | NETCONF/YANG, SNMP | LC→Device | Industry standard for network device management |

### Why This Split?

**REST for request/response:** Validation, approval, and discovery reporting all
follow a request-response pattern where the sender needs to know the outcome before
proceeding. REST maps naturally to this. The overhead of connection setup is
acceptable because these operations are infrequent relative to state updates.

**MQTT for events and broadcasts:** Policy changes, state updates, and event
notifications do not require a response — they are announcements. MQTT's pub/sub
model is purpose-built for this: publishers send once, all interested subscribers
receive it, and QoS levels ensure delivery guarantees match the importance of
the message. Polling (the alternative) wastes bandwidth and adds latency.

---

## Delta-Sync Principle

*Adopted from DISCO (Phemius, Bouet, Leguay, 2014) — validated by IEEE TNSM.*

A key design principle for inter-controller communication: **controllers only
exchange what changed, never the full state.**

This principle has a name in distributed systems research — delta synchronization
(or delta-CRDTs in more formal literature). The practical rule for PDSNO is:

> When a controller needs to inform another controller of a state change, it sends
> only the delta — the record that changed, with its new version number. It does not
> send a full NIB dump or a full policy object.

**Why this matters:** A naive implementation would have controllers periodically
exchange their full state to stay synchronized. This works at small scale and
fails at large scale — the synchronization traffic grows with the number of devices
and the frequency of updates, eventually overwhelming the network and the
controllers themselves.

**How PDSNO implements delta-sync:**
- Every NIB entity has a `version` integer and an `updated_at` timestamp
- When a controller processes a change, it publishes the changed entity (not the full table) to the relevant MQTT topic
- Subscribing controllers receive the delta and merge it into their local NIB view
- If a controller reconnects after being offline, it requests a full resync for the period it was absent — but this is the exception, not the normal operation

---

## Message Envelope Format

Every message exchanged between PDSNO controllers uses a standard envelope,
regardless of which protocol carries it. This makes authentication, logging,
and debugging consistent across all message types.

```json
{
  "envelope": {
    "message_id": "uuid-v4",
    "message_type": "VALIDATION_REQUEST | CHALLENGE | CONFIG_PROPOSAL | ...",
    "sender_id": "regional_cntl_1",
    "recipient_id": "global_cntl_1",
    "timestamp": "2026-02-14T10:30:00.000Z",
    "signature": "hmac-sha256-hex-string",
    "schema_version": "1.0"
  },
  "payload": {
    // message-type-specific content
  }
}
```

**Field definitions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message_id` | UUID string | Yes | Unique identifier for this message — used for deduplication and audit |
| `message_type` | Enum string | Yes | One of the defined message types from `api_reference.md` |
| `sender_id` | String | Yes | The validated controller ID of the sender (not a self-reported temp ID) |
| `recipient_id` | String | Yes | The target controller ID — recipients must verify this matches themselves |
| `timestamp` | ISO-8601 UTC | Yes | When the message was created — used for replay attack detection |
| `signature` | Hex string | Yes | HMAC-SHA256 of the canonical JSON of `envelope + payload`, signed with sender's key |
| `schema_version` | String | Yes | Envelope schema version — allows future backwards-compatible changes |

### Message Authentication

Every message must be signed. Recipients reject unsigned messages unconditionally.

**PoC (Phases 1–5):** HMAC-SHA256 with a shared secret per controller pair. The
shared secret is provisioned during controller validation and stored in the
`context_runtime.yaml` of each controller.

**Phase 6+:** Asymmetric signatures (Ed25519 or ECDSA) using the private key
issued during controller validation. The corresponding public key is stored in
the NIB, so any controller can verify any other controller's messages without
needing a shared secret.

### Replay Attack Prevention

The `timestamp` field and `message_id` field together prevent replay attacks:

1. Recipients reject any message whose `timestamp` is older than `FRESHNESS_WINDOW`
   (default: 5 minutes, configurable in policy)
2. Recipients maintain a short-lived cache of recently seen `message_id` values
   and reject any duplicate within the freshness window

---

## Phase-by-Phase Implementation Plan

### Phase 4 — In-Process Message Bus

Controllers communicate via direct Python function calls wrapped in message
envelope objects. No network involved. The same envelope format is used — this
ensures the transition to REST/MQTT in Phase 6 requires only swapping the
transport layer, not the message format.

```python
# Message bus routes calls directly between controller instances
bus.send(
    sender_id="regional_cntl_1",
    recipient_id="global_cntl_1",
    message=RegistrationRequest(...)
)
```

### Phase 6 — REST + MQTT

- Each controller runs a FastAPI server exposing REST endpoints for each
  request/response message type
- Each controller connects to a shared MQTT broker (Mosquitto for development,
  EMQX or HiveMQ for production)
- Message authentication is enforced at every endpoint — requests without a
  valid signature return `401 Unauthorized`
- Mutual TLS is added for the REST connections at this phase

### Phase 6+ — Full Production

- MQTT QoS levels: `QoS 1` (at-least-once) for state updates, `QoS 2`
  (exactly-once) for policy distribution and audit events
- MQTT topic structure:
  ```
  pdsno/{region}/discovery/reports        # LC → RC discovery submissions
  pdsno/{region}/policy/updates           # GC → RC → LC policy broadcasts
  pdsno/global/events                     # System-wide event log feed
  pdsno/{controller_id}/notifications     # Controller-specific notifications
  ```
- Asymmetric cryptography replaces HMAC for message signing
- Connection-level mTLS in addition to message-level signatures

---

## Timeout and Retry Contracts

Every request/response exchange has a defined timeout and retry behaviour.
These are not arbitrary — they are derived from the operational requirements
of each flow.

| Message Type | Timeout | Max Retries | On Final Failure |
|-------------|---------|-------------|-----------------|
| Validation challenge-response | 30 seconds | 0 (no retry — new flow required) | Reject; write audit entry |
| Config approval request | 60 seconds | 3 (exponential backoff) | Escalate to next tier or deny |
| Discovery report submission | 30 seconds | 3 | Log failure; RC initiates reconciliation |
| Policy distribution | N/A (pub/sub, MQTT handles delivery) | N/A | MQTT QoS guarantees delivery |
| NIB sync notification | N/A (pub/sub) | N/A | Controller requests full resync on reconnect |

**Exponential backoff rule:** Retry 1 waits 1s, retry 2 waits 2s, retry 3 waits
4s. Add ±20% jitter to each wait to prevent thundering herd when multiple
controllers retry simultaneously.

---

## What Controllers Must Not Do

These are communication anti-patterns that the architecture explicitly prohibits:

**No direct NIB-to-NIB communication.** Controllers do not reach into another
controller's NIB directly. All state sharing goes through the defined message
types and the local NIB view update process.

**No polling for state updates.** Controllers do not periodically ask other
controllers "what has changed?" — they subscribe to MQTT topics and receive
updates when changes happen. The one exception is the full resync after a
controller reconnects from an offline period.

**No self-reporting identity in messages.** A controller cannot send a message
claiming to be `global_cntl_1` — the recipient verifies the signature against
the public key registered for that controller ID in the NIB. Identity is
cryptographically verified, not self-asserted.

**No unbounded message sizes.** Large payloads (discovery results for a large
subnet, full policy objects) must be chunked or referenced by ID. The NIB stores
the payload; messages carry a reference to it. This prevents any single message
from overwhelming a controller's message queue.
