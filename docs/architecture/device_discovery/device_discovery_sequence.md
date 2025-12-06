# **PDSNO — Device Discovery Module Documentation**

*Version: Draft — For internal collaborators*

---

## **1. Overview**

The **Device Discovery Module** is responsible for detecting, identifying, and tracking all network devices connected to a PDSNO-managed environment. This module runs primarily on the **Local Controller**, but discovery behavior is influenced by policies propagated from **Global → Regional → Local** tiers.

The design emphasizes:

* Safe scanning
* Policy-driven behavior
* Minimal network disruption
* Dynamic updates
* Resilience and auditability
* Multi-tier governance

This document describes the **current state** of the module as designed and leaves space for future improvements.

---

## **2. High-Level Objectives**

The module aims to:

1. Identify devices dynamically within approved network scopes
2. Support multiple scan modes (incremental and full)
3. Operate safely with strict rate limits
4. Update device inventory automatically and persistently
5. Allow policy inheritance and overrides across controller tiers
6. Log all discovery activities for audit and reporting
7. Retain historical and disconnected devices for diagnostics
8. Enable on-demand triggers alongside scheduled scans

---

## **3. Architectural Placement**

### **Local Controller**

Primary executor of scans
— uses policies received upstream.

### **Regional Controller**

Intermediate governance
— may override or restrict local behavior.

### **Global Controller**

Master policy distributor
— defines core scanning rules for the entire organization.

---

## **4. Discovery Flow (Logic Summary)**

### **Trigger Types**

* **Scheduled discovery** (policy-defined windows)
* **On-demand scans** (API-triggered)
* **Setup-time scans** (first controller initialization)
* **Adaptive interval scans**

  * Critical devices → shorter intervals
  * Non-critical devices → longer intervals

### **Discovery Steps**

1. Local controller receives policy bundle
2. Validates allowed networks, modes, and safety rules
3. Scans per protocols (ARP, LLDP, SNMP, ICMP) within limits
4. Aggregates results
5. Writes/updates device inventory (SQLite)
6. Logs actions locally
7. Sends compressed, signed logs upstream (regional)

---

## **5. Sequence Diagrams**
The sequence through which discovery happens. 

### **5.1 Device Discovery Sequence**

```
 Global Controller
        |
        | 1. Send Global Scan Policy
        v
 Regional Controller
        |
        | 2. Merge + Apply Regional Overrides
        v
 Local Controller
        |
        | 3. Validate + Enforce Local Constraints
        |
        | 4. Start Scan (Scheduled or On-demand)
        |
        |--> [Scan Engine] Run Protocol Probes
        |       - ARP
        |       - ICMP
        |       - LLDP
        |       - SNMP
        |
        | 5. Aggregate Results
        | 6. Update Device Inventory (DB + YAML)
        | 7. Generate Logs (Compress + Sign)
        |
        | 8. Send Summary Upstream
        v
 Regional Controller
        |
        | 9. Store + Forward (if needed)
        v
 Global Controller

```
See .drawio file in
/docs/architecture/device_discovery
```
```


### **5.2 Policy Propagation Diagram**

                +----------------+
                | Global Control |
                +----------------+
                         |
                         | 1. Define/Update Policy
                         v
                +----------------+
                |  Global Policy |
                +----------------+
                         |
                         | 2. Push Policy Downstream
                         v
        -------------------------------------------------
        |                                               |
+----------------+                             +----------------+
| Regional Ctrl 1|                             | Regional Ctrl 2|
+----------------+                             +----------------+
        |                                               |
        | 3. Receive Global Policy                      |
        | 4. Apply Regional Overrides (if any)          |
        |                                               |
        v                                               v
+----------------+                             +----------------+
| Regional Policy|                             | Regional Policy|
+----------------+                             +----------------+
        |                                               |
        | 5. Distribute After-Merge Policies            |
        v                                               v
   -------------------                              -------------------
   |                 |                              |                 |
+----------------+ +----------------+         +----------------+ +----------------+
| Local Ctrl 1A  | | Local Ctrl 1B |         | Local Ctrl 2A  | | Local Ctrl 2B |
+----------------+ +----------------+         +----------------+ +----------------+
       |                |                         |                 |
       | 6. Receive Regional Policy                |                 |
       | 7. Apply Local Overrides (last layer)     |                 |
       |                                            |                 |
       v                                            v                 v
+----------------+                         +----------------+ +----------------+
| Local Policy   |                         | Local Policy   | | Local Policy   |
+----------------+                         +----------------+ +----------------+

                    FINAL POLICY FLOW SUMMARY
                    --------------------------
1. Global defines base policy  
2. Global pushes → regional  
3. Regional applies overrides  
4. Regional distributes to local  
5. Local applies final overrides  
6. Result: **Effective policy** at each local controller


---

## **6. Scan Policy System**

The scan policy governs how discovery behaves across controller tiers.

### **Key Design Choices**

* **Hierarchical governance** ensures global consistency while allowing regional flexibility.
* **Safety-first scanning** to prevent disruption on production networks.
* **Dynamic network scopes** (future feature) will allow auto-population without manual updates.
* **Delegation controls** allow global or regional overrides to enforce compliance.
* **YAML-based policy definitions** simplify readability and versioning.

---

## **7. Current `scan_policy.yaml` Specification**

Below is the **current design**, including placeholders for dynamic features.

```yaml
policy_id: "region-location-scan-version-n"   # Global controller generates this dynamically
version: 1.0

applies_to:
  controller_tier: "local"
  region: "auto-detected-region"

allowed_networks:
  static:                  # For testing only
    - interface: "eth0"
      cidr: "10.10.20.0/24"
      vrf: "default"
      vlan: null
    - interface: "eth1"
      cidr: "192.168.50.0/25"
      vrf: "mgmt"
      vlan: 100

allowed_protocols:
  - arp
  - icmp
  - snmpv2c
  - lldp

prohibited_protocols:
  - telnet
  - ftp
  - tftp
  - ssh  # excluded for safety during discovery

scan_mode:
  default: "incremental"
  allowed_modes:
    - incremental
    - full

schedule:
  window_start: "00:00"
  window_end: "06:00"
  max_scans_per_hour: 4

resource_limits:
  max_threads: 20
  max_concurrent_probes: 100
  probe_timeout_seconds: 2
  max_protocols_parallel: 3

safety:
  max_packet_rate_per_device: 200
  respect_device_blacklist: true
  treat_unknown_devices_as: "suspicious"

delegation:
  allow_regional_override: true
  regional_constraints:
    max_threads: 10
    allowed_protocols:
      - arp
      - icmp

logging:
  batch_size: 200
  compress_before_send: true
  sign_logs: true
  retention_days_local: 7
  retention_days_regional: 30

approval:
  requires_config_push_approval: true
  config_approval_route: "regional"
```

---

## **8. Allowed Network Logic**

### **Design Reasoning**

* Discovery must not accidentally scan unauthorized subnets.
* Networks discovered dynamically in the future will populate the allowed list.
* Static entries are only for **testing** and **initial onboarding**.
* The system will validate every CIDR + interface before scanning.

### **Future Improvements**

* Auto-extract allowed networks from routing tables
* Controller-to-device negotiation for VRFs and VLANs
* Network baseline comparison (detect new/removed networks)

---

## **9. Discovery Engine (Local Controller)**

### **Current Components Designed**

* Protocol list & behavior
* Thread and probe safety limits
* Parallel execution caps
* Incremental vs full logic
* Timeout and fallback rules

### **Components Not Yet Implemented**

* Actual scan executor
* Probe scheduler
* Real-time YAML updater
* SQLite device database writer
* Historical device retention
* Per-protocol driver modules

### **Future Improvements**

* Plugin system for additional protocols
* ML-based device classification
* Adaptive scanning based on past behavior

---

## **10. Inventory & Database Storage**

### **Design Reasoning**

* SQLite chosen for simplicity, atomic writes, and portability
* Device entries will include:

  * MAC
  * IP
  * Interface
  * Protocols detected
  * First seen / last seen
  * Device status
  * Confidence score (future AI integration)

### **Future Improvements**

* Migration to distributed DB for full DSNO
* Incremental snapshot syncing to regional controller
* Query interface for other modules

---

## **11. Logging and Metadata Handling**

### **Current Design**

* Logs stored locally
* Batched for efficiency
* Compressed to reduce bandwidth
* Signed to prevent tampering
* Retention windows defined per tier

### **Future Improvements**

* Unified log viewer
* API endpoint for log streaming
* Cryptographic chaining for audit logs

---

## **12. Governance & Approval Logic**

### **Current Standard**

* Config push actions require regional approval
* Discovery actions follow strict policy boundaries
* Unknown devices flagged automatically

### **Future Improvements**

* Formal approval workflow
* Web dashboard for policy updates
* API for notifying admins of critical discoveries

---

## **13. Completion Status**

As of this document, the Device Discovery module is **~55% complete**, with:

* **Design mostly completed**
* **Implementation not started**
* **Integration pending**

---

## **14. Next Steps**

Recommended roadmap:

1. Implement policy validation schema
2. Build discovery engine scheduler
3. Create YAML autogeneration system
4. Define SQLite schema
5. Implement protocol drivers (start with ARP)
6. Integrate local logging system
7. Simulate discovery workflow in test network

---

## **15. Contribution Notes**

We welcome collaborators to:

* Clean up the current module design
* Help build protocol scanners
* Review safety rules
* Improve diagrams
* Help define the DB schema
* Assist with writing test suites
