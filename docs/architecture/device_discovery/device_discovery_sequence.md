---
title: Device Discovery Sequence
status: Active
author: Alexander Adjei
last_updated: 2026-02-16
component: Device Discovery Module
depends_on: nib_spec.md, communication_model.md, algorithm_lifecycle.md
replaces: device_discovery_sequence.md (previous version was design notes — superseded by this)
---

# Device Discovery Sequence

## Overview

The Device Discovery module is how PDSNO learns what exists in the network.
Every device in the NIB was put there by a discovery cycle. Without discovery,
there is nothing to govern.

This document defines the complete discovery flow: how scans are triggered,
how protocols run in parallel, how results are consolidated into NIB records,
how the LC reports to the RC, how the RC validates and aggregates, how conflicts
and failures are handled, and what gets written to the NIB at every step.

---

## Roles in Discovery

| Controller | Responsibility |
|-----------|---------------|
| **LC** | Runs the actual network scans (ARP, ICMP, SNMP). Owns the raw scan results. Consolidates multi-protocol data per device. Writes to the local NIB view. Reports to RC. |
| **RC** | Receives discovery reports from all LCs in its zone. Validates, deduplicates across LCs. Writes to the regional NIB view. Detects cross-LC anomalies. Reports summary to GC. |
| **GC** | Receives regional summaries. Runs global deduplication (a device seen by two regions). Produces network-wide device inventory. Detects cross-region anomalies. |
| **NIB** | Permanent store for all discovery results. Device Table, Metadata Store, and Event Log are all written during discovery. |

---

## Discovery Trigger Types

Discovery does not only run on a schedule. Four triggers exist:

| Trigger | Who Initiates | When |
|---------|--------------|------|
| **Scheduled** | LC scheduler (cron-like) | Every `policy.discovery_interval` seconds (default: 300s) |
| **On-demand** | RC or GC sends `DISCOVERY_REQUEST` to LC | When a new region comes online, after a config change, after an incident |
| **Event-driven** | LC detects a link-state change event via SBI | When the network signals something changed |
| **Bootstrap** | GC triggers once during system startup | Initial population of the NIB on first deployment |

The flow is the same regardless of trigger — only the initiating event differs.

---

## Discovery Flow Overview

```
GC / RC / Scheduler
       │
       │  Trigger (scheduled / on-demand / event)
       ▼
┌─────────────────────────────────────┐
│         Local Controller            │
│                                     │
│  Stage 1: Build scan targets        │
│  Stage 2: Run parallel scans        │
│           ├── ARP scan              │
│           ├── ICMP ping             │
│           └── SNMP query            │
│  Stage 3: Consolidate per-device    │
│  Stage 4: Diff against NIB          │
│  Stage 5: Write to NIB              │
│  Stage 6: Send report to RC         │
└─────────────────────────────────────┘
                  │
                  │  DISCOVERY_REPORT
                  ▼
┌─────────────────────────────────────┐
│         Regional Controller         │
│                                     │
│  Stage 7: Validate report           │
│  Stage 8: Deduplicate across LCs    │
│  Stage 9: Write to regional NIB     │
│  Stage 10: Send summary to GC       │
└─────────────────────────────────────┘
                  │
                  │  DISCOVERY_SUMMARY
                  ▼
┌─────────────────────────────────────┐
│         Global Controller           │
│                                     │
│  Stage 11: Global deduplication     │
│  Stage 12: Write to global NIB      │
│  Stage 13: Anomaly detection        │
└─────────────────────────────────────┘
```

---

## Stage 1 — LC: Build Scan Targets

```python
def build_scan_targets():
    """
    Determine which subnets and IP ranges to scan for this cycle.
    Pulled from policy — the LC does not decide this itself.
    """
    policy = nib.get_active_policy(scope="local", region=this_controller.region)

    scan_targets = []
    for subnet in policy.discovery_subnets:
        scan_targets.append(ScanTarget(
            subnet=subnet.cidr,           # e.g., "10.0.1.0/24"
            protocols=subnet.protocols,   # ["arp", "icmp", "snmp"]
            snmp_community=subnet.snmp_community,
            timeout_seconds=subnet.scan_timeout or policy.default_scan_timeout
        ))

    if not scan_targets:
        nib.write_event(Event(
            event_type="DISCOVERY_SKIPPED",
            actor=this_controller.assigned_id,
            subject=this_controller.region,
            action="No scan targets in policy — discovery skipped",
            decision="N/A"
        ))
        return []

    return scan_targets
```

**NIB reads:** `get_active_policy()` — gets the subnet list and protocol config.
**NIB writes:** `write_event(DISCOVERY_SKIPPED)` if no targets found.

---

## Stage 2 — LC: Run Parallel Protocol Scans

The three scan types run concurrently using Python's `asyncio` or `ThreadPoolExecutor`.
They are independent — ARP results do not wait for SNMP results.

```python
async def run_parallel_scans(scan_targets):
    """
    Run ARP, ICMP, and SNMP scans concurrently for all targets.
    Returns a dict keyed by MAC address (the stable identifier).
    """
    raw_results = {}  # mac_address → {arp: {...}, icmp: {...}, snmp: {...}}

    tasks = []
    for target in scan_targets:
        if "arp" in target.protocols:
            tasks.append(run_arp_scan(target))
        if "icmp" in target.protocols:
            tasks.append(run_icmp_scan(target))
        if "snmp" in target.protocols:
            tasks.append(run_snmp_scan(target))

    scan_results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in scan_results:
        if isinstance(result, Exception):
            # Individual scan failure — logged but does not abort the whole cycle
            nib.write_event(Event(
                event_type="SCAN_PROTOCOL_FAILED",
                actor=this_controller.assigned_id,
                subject=this_controller.region,
                action=f"Protocol scan failed: {result}",
                decision="N/A"
            ))
            continue

        # Merge into raw_results keyed by MAC
        for mac, data in result.items():
            if mac not in raw_results:
                raw_results[mac] = {}
            raw_results[mac].update(data)

    return raw_results
```

### ARP Scan

```python
async def run_arp_scan(target):
    """
    ARP scan: discovers which IP addresses are active on the subnet
    and maps them to MAC addresses.
    Returns: {mac_address: {ip_address, mac_address, discovery_method: "arp"}}
    """
    results = {}
    try:
        # scapy ARP scan (Phase 5 implementation)
        answered, _ = arping(target.subnet, timeout=target.timeout_seconds, verbose=0)
        for sent, received in answered:
            results[received.hwsrc] = {
                "ip_address": received.psrc,
                "mac_address": received.hwsrc,
                "discovery_method": "arp"
            }
    except Exception as e:
        raise ScanError(f"ARP scan failed for {target.subnet}: {e}")
    return results
```

### ICMP Ping

```python
async def run_icmp_scan(target):
    """
    ICMP ping: confirms reachability of IPs found by ARP (or probes directly).
    Updates existing records with reachability status.
    Returns: {mac_address: {reachable: bool, rtt_ms: float}}
    """
    results = {}
    # Build IP list from subnet
    for ip in ipaddress.ip_network(target.subnet).hosts():
        try:
            rtt = ping(str(ip), timeout=2)
            if rtt is not None:
                # Resolve MAC from IP if not already in raw_results
                mac = arp_resolve(str(ip)) or f"unknown-{ip}"
                results[mac] = {
                    "reachable": True,
                    "rtt_ms": round(rtt * 1000, 2)
                }
        except Exception:
            pass  # Unreachable hosts are simply absent from results
    return results
```

### SNMP Query

```python
async def run_snmp_scan(target):
    """
    SNMP: enriches known devices with vendor info, interfaces, uptime, capabilities.
    Only runs against IPs already confirmed reachable (by ARP or ICMP).
    Returns: {mac_address: {vendor, hostname, interfaces, uptime_seconds, ...}}
    """
    results = {}
    for mac, base_data in known_reachable_devices.items():
        ip = base_data.get("ip_address")
        if not ip:
            continue
        try:
            snmp_data = snmp_get(
                host=ip,
                community=target.snmp_community,
                oids=[
                    OID_SYSTEM_DESCRIPTION,
                    OID_SYSTEM_NAME,
                    OID_IF_TABLE,
                    OID_UPTIME
                ],
                timeout=target.timeout_seconds
            )
            results[mac] = {
                "vendor": parse_vendor(snmp_data.get(OID_SYSTEM_DESCRIPTION)),
                "hostname": snmp_data.get(OID_SYSTEM_NAME),
                "interface_list": parse_if_table(snmp_data.get(OID_IF_TABLE)),
                "uptime_seconds": parse_uptime(snmp_data.get(OID_UPTIME)),
                "snmp_reachable": True
            }
        except SNMPTimeout:
            results[mac] = {"snmp_reachable": False}
        except Exception as e:
            results[mac] = {"snmp_reachable": False, "snmp_error": str(e)}
    return results
```

**NIB writes at Stage 2:** `write_event(SCAN_PROTOCOL_FAILED)` per failed protocol.
All other results are held in memory — not yet written to NIB.

---

## Stage 3 — LC: Consolidate Per-Device

```python
def consolidate_results(raw_results):
    """
    Merge ARP + ICMP + SNMP data for each MAC address into a single
    DeviceRecord per device. MAC address is the stable unique key.
    """
    consolidated = []

    for mac, data in raw_results.items():
        # Classify device type from SNMP description if available
        device_type = classify_device_type(data.get("vendor"), data.get("hostname"))

        # Determine status
        if not data.get("reachable", True) and not data.get("ip_address"):
            status = "unreachable"
        else:
            status = "active"

        device = DeviceRecord(
            mac_address=mac,
            ip_address=data.get("ip_address", ""),
            hostname=data.get("hostname"),
            vendor=data.get("vendor"),
            device_type=device_type,
            region=this_controller.region,
            local_controller=this_controller.assigned_id,
            status=status,
            discovery_method=data.get("discovery_method", "unknown"),
            last_seen=utc_now(),
            metadata=DeviceMetadata(
                snmp_info=data.get("snmp_info"),
                interface_list=data.get("interface_list"),
                uptime_seconds=data.get("uptime_seconds"),
                snmp_reachable=data.get("snmp_reachable", False)
            )
        )
        consolidated.append(device)

    return consolidated
```

---

## Stage 4 — LC: Diff Against NIB

```python
def diff_against_nib(consolidated_devices):
    """
    Compare scan results against what the NIB already knows.
    Classify each device as: NEW, UPDATED, UNCHANGED, or DISAPPEARED.

    Only NEW and UPDATED devices are written back to the NIB —
    no point writing records that haven't changed.
    """
    diff = {
        "new": [],
        "updated": [],
        "unchanged": [],
        "disappeared": []
    }

    scanned_macs = {d.mac_address for d in consolidated_devices}

    for device in consolidated_devices:
        existing = nib.get_device_by_mac(device.mac_address)

        if existing is None:
            diff["new"].append(device)

        elif (existing.ip_address != device.ip_address or
              existing.status != device.status or
              existing.hostname != device.hostname):
            device.entity_id = existing.entity_id  # preserve existing ID
            device.version = existing.version       # for optimistic locking
            diff["updated"].append(device)

        else:
            diff["unchanged"].append(device)

    # Devices in NIB not seen in this scan — may have disappeared
    all_local_devices = nib.get_all_devices(local_controller=this_controller.assigned_id)
    for existing in all_local_devices:
        if existing.mac_address not in scanned_macs:
            # Not seen in this cycle — do not immediately mark as inactive.
            # Must be missed in policy.missed_cycles_before_inactive consecutive
            # cycles before status changes.
            missed = increment_missed_cycles(existing.mac_address)
            if missed >= policy.missed_cycles_before_inactive:
                existing.status = "inactive"
                diff["disappeared"].append(existing)

    return diff
```

---

## Stage 5 — LC: Write to NIB

```python
def write_discovery_results(diff):
    """
    Write only what changed. New devices get a NIB-assigned ID.
    Updated devices preserve their existing ID.
    Disappeared devices get status=inactive.
    """
    written_count = {"new": 0, "updated": 0, "inactive": 0, "conflicts": 0}

    # Write new devices
    for device in diff["new"]:
        device.entity_id = allocate_device_id()  # "nib-dev-<sequence>"
        result = nib.upsert_device(device)
        if result.success:
            written_count["new"] += 1
            nib.write_event(Event(
                event_type="DEVICE_DISCOVERED",
                actor=this_controller.assigned_id,
                subject=device.entity_id,
                action=f"New device: {device.ip_address} ({device.mac_address})",
                decision="N/A"
            ))
        else:
            written_count["conflicts"] += 1
            nib.write_event(Event(
                event_type="DISCOVERY_WRITE_CONFLICT",
                actor=this_controller.assigned_id,
                subject=device.mac_address,
                action=f"NIB write conflict for new device: {result.error}",
                decision="N/A"
            ))

    # Write updated devices
    for device in diff["updated"]:
        result = nib.upsert_device(device)  # version check happens inside upsert
        if result.success:
            written_count["updated"] += 1
            nib.write_event(Event(
                event_type="DEVICE_UPDATED",
                actor=this_controller.assigned_id,
                subject=device.entity_id,
                action=f"Device updated: ip={device.ip_address} status={device.status}",
                decision="N/A"
            ))
        elif result.error == "CONFLICT":
            # Another controller updated this record since we read it
            # Re-read and re-diff — do not overwrite
            written_count["conflicts"] += 1

    # Mark disappeared devices inactive
    for device in diff["disappeared"]:
        result = nib.update_device_status(
            device_id=device.entity_id,
            status="inactive",
            version=device.version
        )
        if result.success:
            written_count["inactive"] += 1
            nib.write_event(Event(
                event_type="DEVICE_INACTIVE",
                actor=this_controller.assigned_id,
                subject=device.entity_id,
                action=f"Device not seen for {policy.missed_cycles_before_inactive} cycles",
                decision="N/A"
            ))

    return written_count
```

**NIB writes at Stage 5:**
- `nib.upsert_device()` — Device Table, new or updated records
- `nib.update_device_status()` — Device Table, inactive devices
- `nib.write_event()` — Event Log: `DEVICE_DISCOVERED`, `DEVICE_UPDATED`,
  `DEVICE_INACTIVE`, `DISCOVERY_WRITE_CONFLICT`

---

## Stage 6 — LC: Send Report to RC

```python
def send_discovery_report(diff, written_count, scan_start_time):
    """
    Send a structured report to the RC. The report is a delta —
    only new, updated, and disappeared devices. Unchanged devices
    are not included to keep the report small.
    """
    report = DiscoveryReport(
        report_id=generate_uuid(),
        lc_id=this_controller.assigned_id,
        region=this_controller.region,
        scan_start=scan_start_time,
        scan_end=utc_now(),
        new_devices=[d.to_dict() for d in diff["new"]],
        updated_devices=[d.to_dict() for d in diff["updated"]],
        inactive_devices=[d.entity_id for d in diff["disappeared"]],
        total_devices_seen=len(diff["new"]) + len(diff["updated"]) + len(diff["unchanged"]),
        write_summary=written_count,
        policy_version=nib.get_active_policy(
            scope="local", region=this_controller.region).policy_version
    )

    nib.write_event(Event(
        event_type="DISCOVERY_REPORT_SENT",
        actor=this_controller.assigned_id,
        subject=report.report_id,
        action=f"Discovery report: {written_count['new']} new, "
               f"{written_count['updated']} updated, "
               f"{written_count['inactive']} inactive",
        decision="N/A"
    ))

    send_to_rc(
        recipient=this_controller.parent_rc_id,
        message_type="DISCOVERY_REPORT",
        payload=report
    )
```

**NIB writes at Stage 6:** `write_event(DISCOVERY_REPORT_SENT)`.

---

## Stage 7 — RC: Validate Report

```python
def handle_discovery_report(report):
    """
    Validate the report from an LC before acting on it.
    Checks: signature, policy version, LC is registered and active.
    """
    # Verify the LC is a registered, active controller
    lc_record = nib.get_controller(report.lc_id)
    if lc_record is None or lc_record.status != "active":
        nib.write_event(Event(
            event_type="DISCOVERY_REPORT_REJECTED",
            actor=this_controller.assigned_id,
            subject=report.report_id,
            action=f"Report from unrecognised or inactive LC: {report.lc_id}",
            decision="REJECTED"
        ))
        return

    # Policy version check
    current_policy = nib.get_active_policy(scope="regional", region=this_controller.region)
    if report.policy_version != current_policy.policy_version:
        nib.write_event(Event(
            event_type="DISCOVERY_REPORT_STALE_POLICY",
            actor=this_controller.assigned_id,
            subject=report.report_id,
            action=f"Report uses policy {report.policy_version}, "
                   f"current is {current_policy.policy_version}",
            decision="FLAGGED"
        ))
        # Do not reject — process the report but flag it.
        # The LC may have been running slightly behind on policy sync.

    nib.write_event(Event(
        event_type="DISCOVERY_REPORT_RECEIVED",
        actor=this_controller.assigned_id,
        subject=report.report_id,
        action=f"Report from {report.lc_id}: {len(report.new_devices)} new devices",
        decision="N/A"
    ))

    process_discovery_report(report, current_policy)
```

---

## Stage 8 — RC: Deduplicate Across LCs

```python
def process_discovery_report(report, policy):
    """
    A device may be visible to more than one LC if it sits at the
    boundary between two LC zones. Deduplication uses MAC address
    as the canonical key — the same MAC from two LCs is the same device.
    """
    for device_data in report.new_devices + report.updated_devices:
        device = DeviceRecord.from_dict(device_data)
        existing = nib.get_device_by_mac(device.mac_address)

        if existing is not None and existing.local_controller != report.lc_id:
            # This device is already registered by a different LC in this region
            # Rule: most recent last_seen wins. The other LC record is updated,
            # not replaced — both observations are valid.
            if device.last_seen > existing.last_seen:
                # New report has fresher data — update the record
                device.entity_id = existing.entity_id
                device.version = existing.version
                nib.upsert_device(device)
                nib.write_event(Event(
                    event_type="DEVICE_LC_REASSIGNED",
                    actor=this_controller.assigned_id,
                    subject=device.entity_id,
                    action=f"Device seen by {report.lc_id} more recently than "
                           f"{existing.local_controller}",
                    decision="N/A"
                ))
            # Both observations recorded in Event Log regardless
            nib.write_event(Event(
                event_type="DEVICE_MULTI_LC",
                actor=this_controller.assigned_id,
                subject=device.entity_id,
                action=f"Device {device.mac_address} seen by multiple LCs: "
                       f"{existing.local_controller} and {report.lc_id}",
                decision="N/A"
            ))
        else:
            # Normal case — device belongs to this LC's zone
            nib.upsert_device(device)
```

---

## Stage 9 — RC: Write Regional NIB and Detect Anomalies

```python
def write_regional_nib_and_detect_anomalies(report, policy):
    """
    After processing the report, check for anomalies that
    a single LC would not be able to detect.
    """
    # Anomaly 1: Device appears in two different regions
    for device_data in report.new_devices:
        device = DeviceRecord.from_dict(device_data)
        cross_region = nib.find_device_in_other_regions(
            mac_address=device.mac_address,
            exclude_region=this_controller.region
        )
        if cross_region:
            nib.write_event(Event(
                event_type="ANOMALY_CROSS_REGION_DEVICE",
                actor=this_controller.assigned_id,
                subject=device.mac_address,
                action=f"Device seen in region {this_controller.region} and "
                       f"{cross_region.region} simultaneously",
                decision="FLAGGED"
            ))

    # Anomaly 2: Sudden large increase in new devices (possible scan injection)
    if len(report.new_devices) > policy.anomaly_new_device_threshold:
        nib.write_event(Event(
            event_type="ANOMALY_DISCOVERY_SPIKE",
            actor=this_controller.assigned_id,
            subject=report.report_id,
            action=f"{len(report.new_devices)} new devices in one cycle — "
                   f"threshold is {policy.anomaly_new_device_threshold}",
            decision="FLAGGED"
        ))
```

---

## Stage 10 — RC: Send Summary to GC

```python
def send_regional_summary(processed_reports):
    """
    Aggregate all LC reports received in this cycle into a
    regional summary for the GC. Only deltas — not full device list.
    """
    summary = RegionalSummary(
        summary_id=generate_uuid(),
        rc_id=this_controller.assigned_id,
        region=this_controller.region,
        cycle_start=cycle_start_time,
        cycle_end=utc_now(),
        total_new=sum(len(r.new_devices) for r in processed_reports),
        total_updated=sum(len(r.updated_devices) for r in processed_reports),
        total_inactive=sum(len(r.inactive_devices) for r in processed_reports),
        total_devices_in_region=nib.count_devices(region=this_controller.region),
        anomalies_flagged=get_cycle_anomalies(cycle_start_time),
        lcs_reported=[r.lc_id for r in processed_reports],
        lcs_missing=get_lcs_that_did_not_report()
    )

    nib.write_event(Event(
        event_type="REGIONAL_SUMMARY_SENT",
        actor=this_controller.assigned_id,
        subject=summary.summary_id,
        action=f"Regional summary: {summary.total_new} new, "
               f"{summary.total_updated} updated, "
               f"{len(summary.lcs_missing)} LCs missing",
        decision="N/A"
    ))

    send_to_gc(
        message_type="DISCOVERY_SUMMARY",
        payload=summary
    )
```

---

## Stages 11–13 — GC: Global Correlation

```python
def handle_regional_summary(summary):
    """
    GC receives summaries from all RCs. Runs global deduplication
    and anomaly detection that spans region boundaries.
    """
    # Stage 11 — Global deduplication
    # A device with the same MAC appearing in two regions is flagged
    # This should not happen in a well-segmented network — it may indicate
    # MAC spoofing, a misconfigured tunnel, or a data error
    all_recent_new_devices = collect_new_devices_from_summary(summary)
    for device in all_recent_new_devices:
        existing_global = nib.get_device_by_mac_global(device.mac_address)
        if existing_global and existing_global.region != summary.region:
            nib.write_event(Event(
                event_type="ANOMALY_GLOBAL_MAC_COLLISION",
                actor=this_controller.assigned_id,
                subject=device.mac_address,
                action=f"MAC {device.mac_address} appears in regions "
                       f"{existing_global.region} and {summary.region}",
                decision="FLAGGED"
            ))

    # Stage 12 — Write global NIB view
    nib.update_global_device_count(
        region=summary.region,
        total=summary.total_devices_in_region
    )
    nib.write_event(Event(
        event_type="GLOBAL_DISCOVERY_CYCLE_UPDATED",
        actor=this_controller.assigned_id,
        subject=summary.summary_id,
        action=f"Global view updated from region {summary.region}",
        decision="N/A"
    ))

    # Stage 13 — Anomaly escalation
    if summary.anomalies_flagged:
        # Anomalies flagged by RC are surfaced to the global level
        # for operator review via the NBI
        escalate_anomalies_to_nbi(summary.anomalies_flagged, summary.region)

    # Alert if an RC is missing entirely from this discovery cycle
    if summary.lcs_missing:
        nib.write_event(Event(
            event_type="DISCOVERY_LC_MISSING",
            actor=this_controller.assigned_id,
            subject=summary.rc_id,
            action=f"LCs did not report: {summary.lcs_missing}",
            decision="FLAGGED"
        ))
```

---

## Error Handling

### Scan Failure (Single Protocol)

A single protocol failing (e.g., SNMP timeout on a device) does not abort
the discovery cycle. The device is still recorded using available data from
the other protocols. The `snmp_reachable=False` field indicates incomplete
enrichment. The Event Log records `SCAN_PROTOCOL_FAILED`.

### Complete Scan Failure (All Protocols)

If all protocols fail for all targets in a subnet — likely a network issue or
LC misconfiguration — the LC writes `DISCOVERY_CYCLE_FAILED` to the Event Log
and notifies the RC. Existing device records are **not** changed — no device is
marked inactive based on a single failed cycle.

```python
def handle_complete_scan_failure(scan_error, scan_targets):
    nib.write_event(Event(
        event_type="DISCOVERY_CYCLE_FAILED",
        actor=this_controller.assigned_id,
        subject=this_controller.region,
        action=f"All scans failed: {scan_error}. "
               f"Targets: {[t.subnet for t in scan_targets]}",
        decision="N/A"
    ))
    notify_rc_scan_failure(
        lc_id=this_controller.assigned_id,
        error=scan_error,
        subnets=[t.subnet for t in scan_targets]
    )
    # Do NOT update any device statuses — stale data is better than false negatives
```

### RC Report Timeout (LC Did Not Report)

If a discovery cycle completes and an LC has not submitted a report within
`policy.lc_report_timeout`, the RC records the missing LC:

```python
def check_lc_report_timeouts():
    for lc_id in this_controller.registered_lcs:
        last_report = nib.get_last_discovery_report_time(lc_id)
        if (utc_now() - last_report).seconds > policy.lc_report_timeout:
            nib.write_event(Event(
                event_type="LC_DISCOVERY_OVERDUE",
                actor=this_controller.assigned_id,
                subject=lc_id,
                action=f"LC has not submitted discovery report in "
                       f"{policy.lc_report_timeout}s",
                decision="FLAGGED"
            ))
            # Trigger an on-demand discovery request to that LC
            send_discovery_request(lc_id, trigger="RC_REQUESTED_OVERDUE")
```

### NIB Write Conflict During Discovery

Discovery writes use optimistic locking. If a conflict occurs — another controller
updated the same device record between the LC's read and write — the LC re-reads
the current record, re-applies only its newer fields, and retries once. If the
retry also conflicts, the LC records the conflict in the Event Log and moves on.
Discovery conflicts are expected and non-critical — the next cycle will converge.

---

## NIB Write Summary

| Stage | NIB Write | Table | Event Type |
|-------|-----------|-------|-----------|
| 1 | `write_event()` | Event Log | `DISCOVERY_SKIPPED` (if no targets) |
| 2 | `write_event()` | Event Log | `SCAN_PROTOCOL_FAILED` (per failed protocol) |
| 5 | `upsert_device()` | Device Table | — |
| 5 | `update_device_status()` | Device Table | — |
| 5 | `write_event()` | Event Log | `DEVICE_DISCOVERED`, `DEVICE_UPDATED`, `DEVICE_INACTIVE`, `DISCOVERY_WRITE_CONFLICT` |
| 6 | `write_event()` | Event Log | `DISCOVERY_REPORT_SENT` |
| 7 | `write_event()` | Event Log | `DISCOVERY_REPORT_RECEIVED`, `DISCOVERY_REPORT_REJECTED`, `DISCOVERY_REPORT_STALE_POLICY` |
| 8 | `upsert_device()` | Device Table | — |
| 8 | `write_event()` | Event Log | `DEVICE_LC_REASSIGNED`, `DEVICE_MULTI_LC` |
| 9 | `write_event()` | Event Log | `ANOMALY_CROSS_REGION_DEVICE`, `ANOMALY_DISCOVERY_SPIKE` |
| 10 | `write_event()` | Event Log | `REGIONAL_SUMMARY_SENT` |
| 11–13 | `write_event()` | Event Log | `ANOMALY_GLOBAL_MAC_COLLISION`, `GLOBAL_DISCOVERY_CYCLE_UPDATED`, `DISCOVERY_LC_MISSING` |
| Error | `write_event()` | Event Log | `DISCOVERY_CYCLE_FAILED`, `LC_DISCOVERY_OVERDUE` |

---

## Design Principles

**MAC address as the stable key.** IP addresses change. Hostnames change.
MAC addresses are hardware-bound and stable. Everything in the discovery
system keys on MAC address for deduplication and identity.

**Delta reporting only.** LCs send only what changed (new, updated, inactive)
to the RC — not a full device list. This keeps report sizes manageable as the
network grows.

**Failed scans do not delete data.** A device not seen in one cycle is not
immediately marked inactive. Multiple missed cycles (configurable) are
required before status changes. This prevents transient network noise from
incorrectly removing valid devices from the NIB.

**Anomaly detection is passive.** The discovery system flags anomalies
(cross-region devices, discovery spikes, MAC collisions) to the Event Log.
It does not take autonomous action on them. A human or a future policy engine
decides what to do with a flagged anomaly.

---

## Future Enhancements (Out of Scope for v1)

- **LLDP/CDP support** — richer topology discovery for managed switches
- **ML-based anomaly detection** — pattern recognition on discovery history
- **Device fingerprinting** — OS and service detection beyond SNMP
- **Intent-based discovery** — discover only what a policy declares relevant
- **Discovery throttling** — reduce scan frequency when network load is high
- **Auto-tagging** — classify device roles from discovery metadata automatically
