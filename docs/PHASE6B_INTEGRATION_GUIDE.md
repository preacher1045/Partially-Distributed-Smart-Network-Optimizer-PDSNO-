# Phase 6B Integration Guide - MQTT Pub/Sub Layer

## Overview
Phase 6B adds MQTT publish-subscribe messaging to PDSNO. Controllers use pub/sub for:
- **Discovery reports**: LC publishes, RC subscribes (no direct addressing)
- **Policy updates**: GC/RC publish, LC/RC subscribe (broadcast)
- **System events**: Any controller publishes, others subscribe

## Why MQTT?

### Problems with Point-to-Point (REST/HTTP):
- LC must know RC's exact address
- RC must know all LC addresses to poll them
- Adding new LC requires updating RC configuration
- High coupling between controllers

### MQTT Pub/Sub Solution:
- LC publishes to topic, doesn't need to know who subscribes
- RC subscribes to topic pattern, automatically receives from all LCs
- Adding new LC: just configure its region, no other changes needed
- Loose coupling, better scalability

---

## What's New

### Components Delivered
1. **MQTT Client** (`mqtt_client.py`) - Pub/sub wrapper around paho-mqtt
2. **LC MQTT Extension** - Publish discovery reports
3. **RC MQTT Extension** - Subscribe to discovery reports, publish policies
4. **Simulation** - End-to-end MQTT demo

### Topic Structure
```
pdsno/
├── discovery/
│   ├── zone-A/
│   │   ├── local_cntl_zone-a_001    # LC publishes here
│   │   └── local_cntl_zone-a_002    # Another LC
│   └── zone-B/...
├── policy/
│   ├── global                        # GC publishes here
│   ├── zone-A                        # RC publishes here
│   └── zone-B
├── events/
│   ├── system                        # System-wide notifications
│   └── zone-A                        # Region-specific events
└── status/
    ├── global_cntl_1                 # Controller heartbeats
    ├── regional_cntl_zone-A_1
    └── ...
```

---

## Prerequisites

### MQTT Broker Required
You need an MQTT broker running. Recommended: **Mosquitto**.

**Installation:**
```bash
# Ubuntu/Debian
sudo apt-get install mosquitto mosquitto-clients
sudo systemctl start mosquitto
sudo systemctl enable mosquitto

# macOS
brew install mosquitto
brew services start mosquitto

# Windows
# Download from: https://mosquitto.org/download/
# Run: mosquitto.exe -v

# Docker
docker run -d --name mosquitto -p 1883:1883 eclipse-mosquitto

# Test broker
mosquitto_pub -h localhost -t test -m "hello"
mosquitto_sub -h localhost -t test
```

---

## Integration Steps

### Step 1: Install Dependencies

```bash
# Add to requirements.txt
paho-mqtt==2.1.0

# Install
pip install paho-mqtt
```

### Step 2: Copy New Files

```bash
# MQTT client
cp pdsno/communication/mqtt_client.py /path/to/your/repo/pdsno/communication/

# Simulation
cp examples/simulate_mqtt_pubsub.py /path/to/your/repo/examples/
```

### Step 3: Update Local Controller

Apply changes from `local_controller_mqtt_extension.py`:

**Key changes:**
1. Add `mqtt_broker` and `mqtt_port` parameters to `__init__()`
2. Create `ControllerMQTTClient` instance
3. Modify `_send_discovery_report()` to try MQTT first, fall back to HTTP/MessageBus
4. Add `connect_mqtt()`, `disconnect_mqtt()`, `subscribe_to_policy_updates()` methods

### Step 4: Update Regional Controller

Apply changes from `regional_controller_mqtt_extension.py`:

**Key changes:**
1. Add `mqtt_broker` and `mqtt_port` parameters to `__init__()`
2. Create `ControllerMQTTClient` instance
3. Add `subscribe_to_discovery_reports()` method
4. Add `_handle_mqtt_discovery_report()` handler
5. Add `publish_policy_update()` method
6. Add `update_mqtt_client_id()` for post-validation ID update

---

## Testing Phase 6B

### Test 1: MQTT Broker Health

```bash
# Terminal 1: Subscribe to test topic
mosquitto_sub -h localhost -t test/topic -v

# Terminal 2: Publish to test topic
mosquitto_pub -h localhost -t test/topic -m "Hello MQTT"

# Expected: Terminal 1 shows "test/topic Hello MQTT"
```

### Test 2: MQTT Pub/Sub Simulation

```bash
# Ensure Mosquitto is running
sudo systemctl status mosquitto  # or brew services list

# Run simulation
python examples/simulate_mqtt_pubsub.py
```

**Expected output:**
```
[1/6] Checking MQTT broker...
✓ MQTT broker is running

[2/6] Initializing infrastructure...
✓ Infrastructure ready

[3/6] Creating Regional Controller with MQTT...
✓ RC connected to MQTT broker
✓ RC subscribed to pdsno/discovery/zone-A/+

[4/6] Creating Local Controller with MQTT...
✓ LC connected to MQTT broker
✓ LC will publish to pdsno/discovery/zone-A/local_cntl_zone-a_001

[5/6] Running discovery cycle...
ARP scan found 53 devices
ICMP scan: 0/53 reachable
SNMP scan: 25/53 responded
✓ Discovery complete:
  - Devices found: 53
  - New devices: 53
  - Report published to MQTT ✓

[6/6] Waiting for RC to receive MQTT message...
[RC] MQTT discovery report from local_cntl_zone-a_001
[RC] Received discovery report from local_cntl_zone-a_001: 53 devices, 53 new

Phase 6B Simulation Complete!
```

### Test 3: Monitor MQTT Traffic

```bash
# Terminal 1: Subscribe to all PDSNO topics
mosquitto_sub -h localhost -t 'pdsno/#' -v

# Terminal 2: Run simulation
python examples/simulate_mqtt_pubsub.py

# Expected: Terminal 1 shows all published messages
```

---

## MQTT Topics Explained

### Discovery Reports
```
Topic: pdsno/discovery/{region}/{lc_id}
Published by: Local Controllers
Subscribed by: Regional Controllers
QoS: 1 (at least once)
Retain: No

Example:
  Topic: pdsno/discovery/zone-A/local_cntl_zone-a_001
  Payload: {discovery report JSON}
  
RC subscribes with wildcard: pdsno/discovery/zone-A/+
  (+ matches any LC ID in zone-A)
```

### Policy Updates
```
Topic: pdsno/policy/global OR pdsno/policy/{region}
Published by: Global Controller (global), Regional Controller (region)
Subscribed by: All controllers in scope
QoS: 1 (at least once)
Retain: Yes (new subscribers get latest policy)

Example:
  Topic: pdsno/policy/zone-A
  Payload: {policy JSON with scan_interval, protocols, etc.}
```

### System Events
```
Topic: pdsno/events/system OR pdsno/events/{region}
Published by: Any controller
Subscribed by: Monitoring systems, other controllers
QoS: 1
Retain: No

Example:
  Topic: pdsno/events/system
  Payload: {event: "controller_down", controller_id: "local_cntl_zone-a_001"}
```

---

## QoS Levels Explained

**QoS 0 (At most once):**
- Message may be lost
- No acknowledgment
- Use for: Heartbeats, non-critical status updates

**QoS 1 (At least once):** ← **PDSNO uses this**
- Message guaranteed to arrive at least once
- May receive duplicates
- Use for: Discovery reports, policy updates

**QoS 2 (Exactly once):**
- Message guaranteed to arrive exactly once
- Highest overhead
- Use for: Critical config changes (future)

---

## Communication Patterns

### Pattern 1: Discovery Reporting (LC → RC)
```
LC1 ─┐
LC2 ─┼─ publish → pdsno/discovery/zone-A/+ → MQTT Broker
LC3 ─┘                                             ↓
                                            subscribe → RC
```
- LCs don't need RC's address
- RC gets reports from all LCs automatically
- New LC? Just configure its region, no RC update needed

### Pattern 2: Policy Distribution (GC → All)
```
GC ─ publish → pdsno/policy/global → MQTT Broker → subscribe ─┬─ RC1
                                                                ├─ RC2
                                                                └─ LC1-N
```
- GC publishes once, all controllers receive
- Retained message ensures new controllers get latest policy

### Pattern 3: Regional Policy (RC → LCs in Region)
```
RC ─ publish → pdsno/policy/zone-A → MQTT Broker → subscribe ─┬─ LC1
                                                                ├─ LC2
                                                                └─ LC3
```
- Regional policies don't affect other regions
- Zone-specific configuration

---

## Fallback Strategy

Controllers use a fallback hierarchy:

1. **Try MQTT** (if configured and connected)
2. **Fall back to HTTP** (if REST enabled)
3. **Fall back to MessageBus** (if in-process mode)

This ensures backwards compatibility and resilience.

---

## Production Considerations

### MQTT Broker Selection

**For Development:**
- **Mosquitto** - Simple, lightweight, easy to setup

**For Production:**
- **EMQX** - High-performance, clustering, monitoring dashboard
- **HiveMQ** - Enterprise features, excellent documentation
- **VerneMQ** - Distributed, good for multi-datacenter

### Security (Phase 6C will add)
- Username/password authentication
- TLS encryption (port 8883)
- Access control lists (ACLs)
- Message payload signing

### Monitoring
```bash
# Monitor broker stats
mosquitto_sub -h localhost -t '$SYS/#' -v

# Monitor all PDSNO traffic
mosquitto_sub -h localhost -t 'pdsno/#' -v | tee mqtt_traffic.log
```

### High Availability
- Run multiple MQTT brokers in cluster
- Use load balancer in front
- Controllers reconnect automatically on broker failure

---

## Troubleshooting

### Issue: "Connection refused" to MQTT broker

**Cause:** Broker not running or wrong host/port

**Fix:**
```bash
# Check if Mosquitto is running
sudo systemctl status mosquitto

# Test connection
mosquitto_sub -h localhost -p 1883 -t test

# Check broker logs
sudo journalctl -u mosquitto -f
```

### Issue: RC not receiving discovery reports

**Cause:** Topic subscription mismatch

**Debug:**
```python
# Add to RC's subscribe_to_discovery_reports()
self.logger.info(f"Subscribing to: pdsno/discovery/{self.region}/+")

# Monitor what LC is publishing
# In LC's _send_discovery_report()
topic = f"pdsno/discovery/{self.region}/{self.controller_id}"
self.logger.info(f"Publishing to: {topic}")
```

### Issue: Messages arriving multiple times

**Cause:** MQTT QoS 1 allows duplicates

**Fix:** This is expected behavior. Handler should be idempotent:
```python
def handle_discovery_report(self, envelope):
    # Use message_id to detect duplicates
    if envelope.message_id in self.processed_messages:
        self.logger.debug(f"Duplicate message {envelope.message_id}, ignoring")
        return
    
    self.processed_messages.add(envelope.message_id)
    # ... process message
```

---

## Verification Checklist

- [ ] MQTT broker installed and running
- [ ] paho-mqtt dependency installed
- [ ] mqtt_client.py copied to repo
- [ ] Local Controller updated with MQTT support
- [ ] Regional Controller updated with MQTT support
- [ ] Can publish to test topic
- [ ] Can subscribe to test topic
- [ ] simulate_mqtt_pubsub.py runs successfully
- [ ] RC receives discovery reports via MQTT
- [ ] Fallback to HTTP/MessageBus still works

Once complete:
✅ **Phase 6B Complete**

Ready for Phase 6C (Message Authentication) or Phase 6D (Multi-Machine Deployment).

---

## What's Next

**Phase 6C: Message Authentication**
- Add HMAC signatures to all messages (both HTTP and MQTT)
- Signature verification at every handler
- Prevent replay attacks with nonces
- Key rotation mechanism

**Phase 6D: Multi-Machine Testing**
- Deploy GC on machine 1
- Deploy RC on machine 2
- Deploy LC on machine 3
- Test cross-network communication
- Measure latency and throughput
