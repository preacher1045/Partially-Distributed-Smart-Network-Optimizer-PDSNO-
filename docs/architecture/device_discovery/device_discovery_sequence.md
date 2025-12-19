1. Why PDSNO Uses a NIB (Network Information Base)

PDSNO's core challenge is coordinating device data, discovery results, and configuration approvals across multiple controllers.

A NIB solves this with a single authoritative state store that all controllers read/write from.

PDSNO Uses the NIB for:

Device discovery state

Device metadata

Device connectivity & health

Device configuration versions

Configuration approval records

Controller operation logs

Policy propagation logs

Change audit trails

Instead of each controller keeping its own memory, the NIB becomes the source of truth.

#️⃣ 2. Hybrid Naming Approach

We use realistic SDN terminology, but keep names simple for contributors.

🔵 NIB Modules (Hybrid)
Module	Description
NIB-Discovery Engine	Handles network scanning, device state insertion, and update rules.
NIB-Device Table	The device DB inside the NIB for discovered devices.
NIB-Metadata Store	Device metadata (type, model, capabilities, etc.)
NIB-Config Table	Tracks config versions and approval status.
NIB-Policy Table	Holds policies pushed by Global → Regional → Local.
NIB-Event Log	Tracks all operations and audits.


#️⃣ 3. PDSNO Architecture Diagram (Text Version)

                       ┌───────────────────────────┐
                       │        GLOBAL CTRL        │
                       │  - Global Policies        │
                       │  - Tier-3 Approvals       │
                       └───────────┬───────────────┘
                                   │
                      Policy Sync  │
                                   ▼
                       ┌───────────────────────────┐
                       │       REGIONAL CTRL        │
                       │  - Localized Policies      │
                       │  - Tier-2 Approvals        │
                       └───────────┬───────────────┘
                                   │
                      Policy Sync  │
                                   ▼
                       ┌───────────────────────────┐
                       │        LOCAL CTRL          │
                       │  - Real-time Control       │
                       │  - Device Discovery        │
                       │  - Tier-1 Approvals        │
                       └───────────┬───────────────┘
                                   │
                                   ▼
                       ┌───────────────────────────┐
                       │       NIB (Central)        │
                       │  Device Table              │
                       │  Metadata Store            │
                       │  Config Table              │
                       │  Policy Table              │
                       │  Event Log                 │
                       └───────────────────────────┘
                                   │
                                   ▼
                       ┌───────────────────────────┐
                       │       NETWORK DEVICES      │
                       └───────────────────────────┘

#️⃣ 4. PDSNO Device Discovery Architecture
Key Roles:
Layer	Responsibility
Local Controller	Scans networks, detects devices, updates NIB.
Regional Controller	Performs sanity checks, aggregates local results.
Global Controller	Performs global correlation, resolves duplicates, generates network-wide reports.
NIB	Stores results permanently and provides a unified view.
Discovery Flow (Simplified)

Global Controller requests discovery → initial bootstrap.

Local Controller runs discovery (scheduled + on-demand).

Results pushed to NIB-Discovery Engine.

NIB updates:

Device Table

Metadata Store

Device state flags (new, updated, unreachable, etc.)

Regional Controller validates and aggregates.

Global Controller synchronizes and checks for anomalies.

#️⃣ 5. Device Discovery Design Logic (Human-friendly)
✔ Should support:

Periodic discovery

On-demand discovery

Differential updates

Disconnect detection

Auditable history

Multi-controller contributions

Cross-layer consistency

✔ Should minimize:

Over-scanning

Duplicate discovery

Network congestion

Conflicting updates

Out-of-sync controllers

✔ Should be:

Modular

Extensible

Plug-in friendly

Easily testable

Documented

#️⃣ 6. Planned Improvements (Leaves room for growth)
Future improvements you will add later:

ML-based anomaly detection

Auto-tagging devices

Fingerprinting enhancements

Multi-protocol discovery plugins (LLDP, ARP, ICMP, SNMP, custom)

Event-driven discovery triggers

Discovery throttling based on network load

Intent-based discovery (discover only what’s needed)