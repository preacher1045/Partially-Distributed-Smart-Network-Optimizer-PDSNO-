---
title: Deployment Guide
status: Active
author: Alexander Adjei
last_updated: 2026-02-16
depends_on: architecture.md, CONTRIBUTING.md
---

# PDSNO — Deployment Guide

## PoC Deployment (Phase 1–5)

The PoC runs all controllers as Python processes on a single machine or across
a small local network. No cloud infrastructure required.

### Prerequisites

```bash
Python 3.11+
SQLite 3.35+ (ships with Python)
pip packages: see requirements.txt
```

### Repository Structure

```
pdsno/
├── controllers/
│   ├── global_controller.py
│   ├── regional_controller.py
│   └── local_controller.py
├── data/
│   ├── nib_store.py          # NIBStore interface
│   ├── models.py             # NetworkEntity, Device, ConfigRecord, etc.
│   └── migrations/
├── algorithms/
│   ├── discovery/
│   │   ├── arp_scan.py
│   │   ├── icmp_ping.py
│   │   └── snmp_query.py
│   └── validation/
│       └── controller_validation.py
├── communication/
│   ├── message_bus.py        # In-process bus for PoC phases
│   ├── rest_server.py        # Phase 6
│   └── mqtt_client.py        # Phase 6
├── config/
│   ├── context_runtime.yaml  # Per-controller runtime config
│   └── policy_default.yaml   # Default policy values
├── tests/
└── docs/
```

### Starting the PoC (Single Machine)

```bash
# 1. Clone and install
git clone https://github.com/<your-org>/pdsno.git
cd pdsno
pip install -r requirements.txt

# 2. Initialize the NIB (creates SQLite DB with schema)
python -m pdsno.data.init_nib --env dev

# 3. Start Global Controller
python -m pdsno.controllers.global_controller \
  --config config/context_runtime.yaml \
  --role global --id global_cntl_1

# 4. Start Regional Controller (in a new terminal)
python -m pdsno.controllers.regional_controller \
  --config config/context_runtime.yaml \
  --role regional --region zone-A \
  --parent global_cntl_1

# 5. Start Local Controller (in a new terminal)
python -m pdsno.controllers.local_controller \
  --config config/context_runtime.yaml \
  --role local --region zone-A \
  --parent regional_cntl_zoneA_1 \
  --subnets 10.0.1.0/24
```

### context_runtime.yaml

Each controller reads its runtime config from this file:

```yaml
controller:
  id: auto_assigned           # Set by validation flow
  role: auto_determined
  region: zone-A
  parent_id: null             # Set after validation

nib:
  backend: sqlite
  path: ./data/pdsno.db
  wal_mode: true

communication:
  mode: in_process            # Phase 1-5: in_process | Phase 6: rest+mqtt
  rest_port: 8080             # Phase 6
  mqtt_broker: localhost:1883 # Phase 6

policy:
  discovery_interval: 300
  missed_cycles_before_inactive: 3
  lc_report_timeout: 600
  emergency_rate_limit_per_hour: 5

security:
  signing_key: null           # Set during validation
  cert: null                  # Set during validation
  freshness_window_seconds: 300
```

---

## Phase 6 Deployment (REST + MQTT)

### Infrastructure Requirements

```
1x MQTT broker (Mosquitto for dev, EMQX for production)
1x PostgreSQL instance (Phase 6 NIB backend)
1x Redis instance (Phase 6 transient NIB tier)
Python 3.11+ on each controller host
```

### Scaling Guidelines

| Tier | Recommended instances | Notes |
|------|-----------------------|-------|
| Global Controller | 1 primary + 1 standby | Failover not yet designed — standby is warm but manual |
| Regional Controller | 1 per geographic zone | Scale zones not instances |
| Local Controller | 1 per /24 subnet block (guideline) | Tune based on device count and scan frequency |

### Network Requirements

| Connection | Protocol | Port | Required |
|-----------|---------|------|---------|
| LC → RC | REST/HTTPS | 8443 | Yes |
| RC → GC | REST/HTTPS | 8443 | Yes |
| All → MQTT broker | MQTT over TLS | 8883 | Yes (Phase 6) |
| LC → Network devices | SNMP | 161/UDP | Yes |
| LC → Network devices | ICMP | — | Yes |
| External → GC NBI | REST/HTTPS | 443 | Optional |

---

## Running Tests

```bash
# Unit tests (no network required)
pytest tests/unit/ -v

# Integration tests (requires local NIB + in-process bus)
pytest tests/integration/ -v

# Discovery tests (requires a real or simulated subnet)
pytest tests/discovery/ -v --subnet 10.0.1.0/24
```

---

## Common Issues

**NIB write conflicts during tests:** Expected. The optimistic locking retry logic
handles this. If you see high conflict rates in production, it means multiple
controllers are scanning the same subnet — check policy subnet assignments.

**SNMP timeouts during discovery:** Normal for devices without SNMP enabled.
Device is still recorded from ARP/ICMP data; SNMP enrichment is optional.

**Challenge timeout during controller validation:** Usually a clock skew issue.
Ensure all controller hosts have NTP synchronized. The freshness window is 5 minutes
by default — generous for any reasonable clock drift.

**Bootstrap token already consumed:** A controller trying to register a second time
with the same bootstrap token will be rejected. Re-provision the controller with a
fresh token via the provisioning process.
