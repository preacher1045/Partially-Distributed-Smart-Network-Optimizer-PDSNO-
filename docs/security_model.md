---
title: Security Model
status: Active
author: Alexander Adjei
last_updated: 2026-02-16
depends_on: architecture.md, nib/nib_spec.md, verification/controller_validation_sequence.md
---

# PDSNO — Security Model

## Trust Boundaries

PDSNO operates on a zero-trust model between controllers. No controller is implicitly trusted because it is on the same network. Trust is earned through validation and maintained through cryptographic proof on every message.

```
UNTRUSTED                    TRUST BOUNDARY                    TRUSTED
─────────────────────────────────────────────────────────────────────
Unvalidated controller  ──[Validation flow]──►  Validated controller
External application    ──[NBI auth]──────────►  Authorized client
Network device          ──[SBI credentials]───►  Managed device
```

---

## Security Properties by Component

### Controller Identity
- Every controller has a cryptographically assigned identity issued by a higher-tier controller
- Identity is bound to: assigned ID, role, region, public key, issuing controller, expiry
- PoC: HMAC-SHA256 signed JSON certificate. Phase 6+: Ed25519 asymmetric certificate
- Identities expire and must be renewed — no permanent trust

### Message Authentication
- Every inter-controller message carries an HMAC-SHA256 signature (PoC) over the full envelope + payload
- Recipients reject unsigned messages unconditionally
- Replay prevention: `timestamp` freshness window (5 min) + `message_id` deduplication cache

### Config Change Governance
- No config executes without a signed execution token from an approving controller
- Tokens are single-use, time-bounded, bound to specific proposal + devices + config hash
- Sensitivity classification is always re-done by the approving tier — LC suggestions are advisory only
- Emergency executions are rate-limited, type-restricted, and always audit-logged

### NIB Integrity
- Event Log is append-only — no UPDATE or DELETE permitted by database trigger
- All Event Log entries are signed by the controller that wrote them
- Config approval records are immutable once written

### Discovery Security
- Discovery results are validated by RC before entering the regional NIB view
- Reports from unrecognised or inactive LCs are rejected
- Anomaly spikes (unusual numbers of new devices) trigger flagging, not silent acceptance

---

## Threat Model Summary

| Threat | Mitigation | Document |
|--------|-----------|---------|
| Rogue controller joins network | Validation flow — challenge/response + bootstrap token + policy checks | `controller_validation_sequence.md` |
| Stolen bootstrap token used | Token is single-use; challenge-response still required even with valid token | `controller_validation_sequence.md` |
| LC spoofs LOW sensitivity for HIGH change | RC independently re-classifies every proposal | `config_approval_logic.md` |
| Emergency mode used as governance bypass | Rate limiting + restricted config types + mandatory audit + post-facto RC/GC acknowledgement | `config_approval_logic.md` |
| Execution token replayed | Single-use; consumed before execution begins; bound to config hash + devices | `config_approval_logic.md` |
| Partial execution + network failure | Execution state written to NIB before device is touched; reconciliation on reconnect | `config_approval_logic.md` |
| Concurrent conflicting config approvals | Approval-time device locking via NIB Controller Sync Table | `nib_spec.md` |
| Forged audit logs | Signed entries; cross-validated with NIB device state; append-only | `nib_spec.md` |
| Discovery scan injection | RC validates report source; anomaly threshold flags spikes | `device_discovery_sequence.md` |
| MAC spoofing across regions | GC MAC collision detection flags cross-region duplicates | `device_discovery_sequence.md` |
| Replay attack on validation request | Timestamp freshness window + message_id deduplication | `communication_model.md` |

Full threat scenarios and mitigations: `docs/architecture/policy_propagation/threat_model_and_mitigation.md`

---

## Security Phases

| Phase | Capability |
|-------|-----------|
| PoC (1–5) | HMAC-SHA256 message signing, shared secrets, signed JSON certificates, single-use tokens, append-only Event Log |
| Phase 6 | Asymmetric cryptography (Ed25519), mutual TLS on REST connections, MQTT over TLS, certificate rotation |
| Phase 7+ | Key management service integration, HSM support for GC signing keys, formal RBAC model |
