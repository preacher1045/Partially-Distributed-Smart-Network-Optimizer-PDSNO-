---
title: Vendor Gap Analysis — PDSNO Competitive Positioning
status: Living Document — Update as research and customer conversations develop
author: Alexander Adjei
last_updated: 2026-02-14
purpose: >
  Maps documented shortcomings of major proprietary network orchestration platforms
  to PDSNO capabilities. This document serves two purposes:
  (1) Technical — guides which features PDSNO must prioritize to be genuinely useful
  (2) Commercial — forms the foundation of the sales and partnership narrative
---

# PDSNO — Vendor Gap Analysis & Competitive Positioning

## How to Use This Document

This is a **living document**. Every section has three parts:

- **The gap** — what the vendor's product does not do well, supported by evidence
- **PDSNO's response** — what the architecture already addresses or plans to address
- **Maturity status** — how far along PDSNO is in actually closing this gap

Update this document as you learn more through customer conversations. Real feedback from
network engineers trumps any research — when a practitioner tells you their specific pain,
write it down here with a date and source label (anonymized if needed).

---

## Positioning Statement

PDSNO does not compete with Cisco ACI, VMware NSX, or Juniper Apstra.
It augments them.

The target customer is an organization that already runs one or more of these platforms
and experiences the gaps described below. PDSNO sits **above** their existing tools as a
coordination and governance layer — pulling state from each vendor's API, enforcing
consistent policy across all of them, and providing a unified audit trail that none of
them deliver alone.

The value proposition in one sentence:
**"PDSNO gives you control and visibility across your entire network, not just the parts
your vendor covers."**

---

## Gap 1 — Vendor Lock-In at the Orchestration Layer

### The Problem

Cisco ACI delivers its full benefits only on Cisco Nexus hardware. VMware NSX delivers its
full benefits only within the VMware hypervisor stack. Most enterprise organizations run
both, plus additional hardware from other vendors, plus cloud infrastructure. Each vendor's
orchestration tool manages its own domain well and the rest of the network poorly or not at
all.

The result is that network engineers operate multiple dashboards, multiple policy systems,
and multiple audit trails — one per vendor — with no single place to see or govern the
whole network. Manual reconciliation between these systems is where errors happen and where
incidents are slow to diagnose.

This is not a criticism of any single vendor. It is a structural property of the market:
each vendor has an incentive to make their tool excellent within their ecosystem and
indifferent to everything outside it.

**Evidence from the market:**
Juniper's acquisition of Apstra was explicitly motivated by customer demand for
multi-vendor management. Apstra's value proposition was intent-based networking across
vendors — customers wanted it enough that Juniper paid to acquire it rather than build it.
The fact that a company was acquired for this capability confirms the gap is real and valued.

VMware NSX users report that "extending integration to third-party systems or non-VMware
environments can be challenging" and that "additional components often require separate
appliances or software." This is a consistent theme in practitioner reviews.

### PDSNO's Response

PDSNO's architecture is vendor-agnostic by design. The controller hierarchy (Global →
Regional → Local) does not assume any specific vendor at any layer. The NIB stores device
state regardless of what vendor manufactured the device or what tool discovered it.

**The specific capability needed:** A vendor adapter layer — a set of modules that connect
to each major vendor's northbound API and pull device state, topology, and events into the
NIB. Once in the NIB, all PDSNO capabilities apply to that data uniformly.

**Planned adapters (in priority order):**

| Adapter | Target API | Priority | Phase |
|---------|-----------|----------|-------|
| Cisco ACI Adapter | APIC REST API (northbound) | High | Phase 7 |
| VMware NSX Adapter | NSX Manager REST API | High | Phase 7 |
| Juniper Junos Adapter | Junos REST API / NETCONF | Medium | Phase 8 |
| Generic NETCONF Adapter | RFC 6241 — covers many vendors | Medium | Phase 8 |
| Generic SNMP Adapter | SNMP v2c/v3 — fallback for legacy | Low | Phase 8 |

**Maturity:** Architecture designed. Implementation planned for Phase 7.
Not yet implemented.

---

## Gap 2 — Multi-Domain Policy Consistency

### The Problem

When an organization runs Cisco ACI in its data center, VMware NSX in its virtualization
layer, and a third-party SD-WAN at its branches, there is no single system that enforces
consistent policy across all three. Each tool has its own policy model, its own syntax, and
its own enforcement mechanism.

A compliance requirement — for example, "no unencrypted traffic between VLAN 10 and the
internet" — must be manually translated into three different policy configurations in three
different tools. When the policy needs to change, it must be updated in all three
simultaneously. Drift between them is not detected automatically. Audit evidence of
compliance is scattered across three separate logs.

For regulated industries (banking, healthcare, government, critical infrastructure), this
is not just an operational headache — it is a compliance liability. Auditors ask for a
unified policy audit trail and most organizations cannot produce one.

**Evidence from the market:**
Cisco's own documentation describes ACI's policy model as applying to its fabric. The
northbound APIs allow third-party systems to read and write policy — but the translation
layer and consistency enforcement between multiple vendor policy engines is left to the
customer to build. VMware NSX has the same property within its domain.

Cisco ACI's Multi-Site Orchestrator (Nexus Dashboard Orchestrator) addresses this problem
partially — but only across multiple Cisco ACI fabrics, not across Cisco + VMware + others.

### PDSNO's Response

PDSNO's policy propagation system is designed exactly for this problem. The Global
Controller holds the canonical policy. Regional Controllers enforce it within their zones.
The distribution mechanism is version-controlled and auditable — every policy version is
stored with a timestamp and the identity of the controller that distributed it.

**The specific capability needed:** A policy translation layer — the ability to take a
PDSNO policy definition and translate it into the native format required by each vendor's
API. A Cisco ACI adapter would translate PDSNO policy into APIC tenant/EPG/contract
constructs. A VMware NSX adapter would translate into NSX security groups and distributed
firewall rules.

This is technically non-trivial because each vendor's policy model has different
abstractions. The approach is to define a **PDSNO Common Policy Model** — a
vendor-neutral representation — and then build per-vendor translators.

**Maturity:** Policy propagation architecture designed and documented.
Common Policy Model not yet defined. Translation adapters not yet implemented.
This is Phase 8–9 work.

---

## Gap 3 — Cross-Domain Change Governance and Auditability

### The Problem

When a configuration change touches multiple vendor domains — for example, a firewall
rule change that requires updates in Cisco ACI, VMware NSX, and a branch SD-WAN
simultaneously — there is no single tool that:

- Requires approval before the change is applied across all three
- Issues a single execution token that authorizes the change
- Ensures all three changes succeed or all three roll back
- Produces a single audit record that covers the entire cross-domain change

Each vendor's tool has its own change management workflow, its own approval mechanism,
and its own audit log. Reconstructing what happened across all three after an incident
is a manual, time-consuming process.

For organizations subject to SOX, PCI-DSS, HIPAA, or NIS2 compliance requirements,
the inability to produce a unified change audit trail is a real and recurring problem
during audits.

**Evidence from the market:**
VMware's own product guide notes that NSX "is not a comprehensive regulatory compliance
solution and should not be construed as legal or regulatory advice" — confirming the
compliance gap is acknowledged even by the vendor.

Real user reviews note that VMware NSX has "logs everywhere — on Edge servers, vCenter,
or ESXi" making troubleshooting difficult. This reflects the absence of a unified audit
log, not just for compliance purposes but for operational incident response.

### PDSNO's Response

PDSNO's configuration approval logic is purpose-built for this problem. Key capabilities:

- **Sensitivity tiers** — changes are classified LOW/MEDIUM/HIGH/EMERGENCY with
  appropriate approval paths for each
- **Execution tokens** — cryptographically signed, single-use, bound to the specific
  change, devices, and time window. A change cannot be executed without a valid token.
- **Unified audit log** — the NIB Event Log captures every proposal, approval, execution,
  and rollback with a signed entry, regardless of which vendor domain the change touches
- **Rollback support** — rollback instructions are stored at proposal time so they are
  available immediately if execution fails

**The specific capability this creates for regulated customers:**
A compliance report that shows, for any time period: every change proposed, who proposed
it, who approved it, when it was applied, and what the before/after state was — across
all vendor domains in a single document. This is currently impossible with vendor-native
tools alone.

**Maturity:** Configuration approval logic designed and documented in detail.
Implementation planned for Phase 7. Compliance report output not yet designed.

---

## Gap 4 — Cross-Tier Incident Correlation

### The Problem

When a network incident occurs in a multi-vendor environment, correlating events across
vendor domains to reconstruct the incident timeline is extremely difficult. Cisco ACI
has its own fault logs. VMware NSX has events in its own system. The physical switches
have syslog. The SD-WAN has its own telemetry.

An incident that starts as a routing anomaly on a physical switch can manifest as
application timeouts in the VMware layer, trigger alerts in the monitoring system, and
cause secondary failures in other domains — all within seconds. No vendor-native tool
sees the full picture because no single vendor owns the full stack.

Network engineers spend significant time in incident response manually correlating
timestamps and events across these separate systems. Mean time to resolution (MTTR) is
longer than it needs to be because the correlation is manual.

**Evidence from the market:**
VMware NSX user reviews note the product has "its own definition of terms and design,
making it difficult to troubleshoot." This is a symptom of the isolation problem — NSX
uses its own terminology and its own log format, which does not map naturally onto what
the physical network layer is reporting.

Juniper's AI-driven telemetry (Mist AI) is a partial answer but is, again, scoped to
Juniper's own ecosystem. It does not correlate with events from Cisco or VMware domains.

### PDSNO's Response

The NIB's unified Event Log is the foundation for cross-tier incident correlation. Because
all controllers — regardless of which vendor domain they monitor — write to the same Event
Log with a consistent format and UTC timestamps, correlating events across domains becomes
a query rather than a manual reconstruction exercise.

**The specific capability this creates:**
Given an incident timestamp, PDSNO can produce a timeline of all events across all vendor
domains that were recorded in the NIB within a defined window around that timestamp.
This is the equivalent of a unified syslog that spans vendor boundaries.

**A future enhancement that amplifies this significantly:**
When the vendor adapters (Gap 1) are built, they will pull events from each vendor's API
into the NIB Event Log in real time. At that point, PDSNO becomes a true cross-domain
event correlation engine — not just for PDSNO-originated changes, but for anything
happening across the managed infrastructure.

**Maturity:** NIB Event Log designed and specified. Cross-domain correlation query
interface not yet designed. Vendor event ingestion not yet implemented.

---

## Gap 5 — Complexity and Learning Curve for Multi-Vendor Operations

### The Problem

Each major vendor's orchestration platform has a steep learning curve. Cisco ACI's
policy model is powerful but complex — EPGs, contracts, bridge domains, VRFs, and
tenants require significant training to use correctly. VMware NSX has a similarly steep
learning curve and, as user reviews consistently note, "API usage for configurations not
accessible via the GUI further heightens the complexity."

When an organization runs both Cisco ACI and VMware NSX, their network engineers must
be proficient in both policy models simultaneously. Hiring for this combination of skills
is expensive. Training existing staff takes time. Operational errors increase when
engineers work across unfamiliar abstractions.

This problem compounds at scale: a large enterprise or ISP with multiple regional data
centers may have different vendor footprints in different regions, meaning the
operational complexity is multiplied further.

### PDSNO's Response

PDSNO does not eliminate the need to understand vendor-native tools — that would be
unrealistic. What it can do is reduce how often engineers need to drop into vendor-native
interfaces for common governance tasks.

The specific operational tasks that PDSNO centralizes — change approval, policy
distribution, audit logging, controller validation — are tasks that currently require
navigating each vendor's interface separately. By centralizing these in PDSNO, engineers
can manage governance from a single interface even if the underlying execution happens in
vendor-native systems.

**This is a long-term positioning advantage.** As PDSNO's vendor adapters mature, the
abstraction layer grows. The goal is not to replace vendor UIs for configuration — it is
to make governance, auditing, and cross-domain change management something an engineer
does in one place.

**Maturity:** Architecture supports this vision. UI layer not yet designed or implemented.
This is Phase 8+ work.

---

## Competitive Landscape Summary

| Company | Product | What They Do Well | Where PDSNO Augments |
|---------|---------|-------------------|---------------------|
| Cisco | ACI / APIC | Policy automation within Cisco fabric | Multi-vendor coordination, cross-domain audit |
| VMware/Broadcom | NSX | Network virtualization within VMware stack | Cross-domain governance, simplified compliance reporting |
| Juniper | Apstra | Intent-based networking, multi-vendor support | Strongest overlap — monitor Apstra development closely |
| Nokia | NSP | Telco-grade orchestration | PDSNO targets enterprise/ISP tier below telco-grade complexity |
| HashiCorp | Terraform | Infrastructure-as-code, cross-vendor provisioning | Different layer — Terraform provisions, PDSNO governs |
| Red Hat | Ansible | Automation and configuration management | Different layer — Ansible executes, PDSNO governs and audits |

**The most important row is Juniper Apstra.** Apstra is the closest existing product to
what PDSNO is building. It was acquired by Juniper precisely because it solved the
multi-vendor management problem. Key differences to track:

- Apstra is now owned by Juniper, which creates a commercial incentive to favor Juniper
  hardware over time — PDSNO has no such incentive
- Apstra is enterprise software with enterprise pricing — PDSNO as open-source creates
  a different access model
- Apstra's governance and change approval capabilities are less developed than PDSNO's
  designed architecture — this may be a genuine differentiation point

---

## Target Customer Profiles

Based on the gap analysis, the following customer profiles are most likely to feel these
gaps acutely and be willing to adopt a new solution to address them:

**Profile 1 — Regional ISP or Telecoms Provider**
Operates a multi-vendor network across multiple geographic regions. Has compliance
requirements. Struggles with change governance across regions. Team size: 5–20 network
engineers.

**Profile 2 — Mid-Size Financial Services Firm**
Runs Cisco ACI in data center, VMware NSX for virtualization. Under PCI-DSS and
potentially SOX compliance. Audit findings related to change management and policy
consistency are recurring pain points. Team size: 10–30 network engineers.

**Profile 3 — Large University or Research Institution**
Complex mixed-vendor network. Multiple departments with different needs. Central IT
team responsible for governance. Open-source adoption is culturally comfortable.
Team size: 5–15 network engineers.

**Profile 4 — Manufacturing Company with OT/IT Convergence**
Operational technology (OT) networks converging with IT networks. Multiple vendors.
Security and change governance are critical due to production environment sensitivity.
Team size: varies widely.

---

## Customer Discovery Questions

When talking to potential customers (network engineers at the above types of
organizations), these questions will validate or refute the gaps above.

Use these conversations to update this document. A gap confirmed by five real
practitioners is worth more than any amount of market research.

1. "How many different network management tools or dashboards does your team use day-to-day?"
2. "When you need to make a change that touches more than one vendor's equipment, what does that process look like?"
3. "When something goes wrong in your network, what does the troubleshooting process look like? How do you reconstruct what happened?"
4. "If you had to show an auditor a complete record of every network change made in the last 90 days, how would you produce that?"
5. "What's the most painful part of managing your network that you wish someone would solve?"
6. "Are you able to enforce consistent security policy across all parts of your network, or are there gaps between vendor domains?"

---

## What to Track Going Forward

Add entries here as new information becomes available.

### Vendor Product Updates to Monitor

- **Cisco Nexus Dashboard Orchestrator** — Cisco is actively expanding NDO's
  multi-site and multi-domain capabilities. Track whether they close the cross-vendor
  gap themselves. If they do, reassess Gap 1.
- **Juniper Apstra** — Monitor feature releases. If Juniper deprioritizes multi-vendor
  support (which their ownership incentive suggests they might), that is a market
  opportunity.
- **VMware NSX under Broadcom** — Broadcom's acquisition of VMware has caused customer
  uncertainty and price increases. Some NSX customers are evaluating alternatives.
  This creates a window.

### Regulatory Developments to Monitor

- **NIS2 Directive (Europe)** — Increases network security and audit requirements for
  critical infrastructure operators. Effective 2024–2025. Organizations subject to NIS2
  will need better change governance tooling.
- **DORA (Digital Operational Resilience Act, EU)** — Applies to financial services.
  Requires demonstrable operational resilience including network change management.
  Effective January 2025.
- **US CISA guidance on network security** — Ongoing. Any new requirements for
  federal contractors or critical infrastructure create demand for audit tooling.

---

*Last updated: February 2026*
*Next review: When first customer discovery conversations are completed*
