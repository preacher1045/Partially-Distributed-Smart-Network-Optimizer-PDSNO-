# Phase 6A Integration Guide - REST Communication Layer

## Overview
Phase 6A replaces the in-process MessageBus with real HTTP communication using FastAPI. Controllers now run as separate processes and communicate over the network.

## What's New

### Architecture Change
**Before (Phase 5):**
```
All controllers in same process
    ↓
MessageBus (function calls)
    ↓
Direct Python function invocation
```

**After (Phase 6A):**
```
Each controller in separate process
    ↓
HTTP POST requests
    ↓
FastAPI REST endpoints
```

### Key Benefits
- Controllers can run on different machines
- Real network communication with timeouts/retries
- Standard REST API for external integrations
- Better fault isolation (one controller crash doesn't kill others)

---

## Files Delivered

### New Files (4)
1. `pdsno/communication/rest_server.py` - FastAPI server for controllers
2. `pdsno/communication/http_client.py` - HTTP client replacing MessageBus
3. `examples/simulate_rest_communication.py` - Multi-process demo
4. `phase6a_requirements_additions.txt` - New dependencies

### Files to Modify (2)
1. `pdsno/controllers/global_controller.py` - Add REST server support
2. `pdsno/controllers/regional_controller.py` - Add REST server + HTTP client

---

## Integration Steps

### Step 1: Install Dependencies

```bash
# Add to requirements.txt:
fastapi==0.115.5
uvicorn[standard]==0.32.1
python-multipart==0.0.18
httpx==0.28.1

# Install
pip install -r requirements.txt
```

### Step 2: Copy New Files

```bash
# REST infrastructure
cp pdsno/communication/rest_server.py /path/to/your/repo/pdsno/communication/
cp pdsno/communication/http_client.py /path/to/your/repo/pdsno/communication/

# Simulation
cp examples/simulate_rest_communication.py /path/to/your/repo/examples/
```

### Step 3: Update Global Controller

Open `pdsno/controllers/global_controller.py` and apply changes from:
`global_controller_rest_extension.py`

**Key changes:**
1. Add `ControllerRESTServer` import
2. Add `enable_rest` and `rest_port` parameters to `__init__()`
3. Create and configure `self.rest_server`
4. Register message handlers with REST server
5. Add `start_rest_server_background()` method

### Step 4: Update Regional Controller

Open `pdsno/controllers/regional_controller.py` and apply changes from:
`regional_controller_rest_extension.py`

**Key changes:**
1. Add `ControllerRESTServer` and `ControllerHTTPClient` imports
2. Replace `message_bus` with `http_client` parameter
3. Modify `request_validation()` to support HTTP
4. Modify `_handle_challenge()` to support HTTP
5. Add REST server setup in `__init__()`
6. Add `start_rest_server_background()` and `update_rest_server_id()` methods

### Step 5: Update Local Controller (Optional)

Local Controller can also be updated similarly, but it's not required for Phase 6A since discovery reports work over HTTP between LC and RC.

---

## Testing Phase 6A

### Test 1: Simple Health Check

```bash
# Terminal 1: Start Global Controller
python -c "
from pdsno.controllers.global_controller import GlobalController
from pdsno.controllers.context_manager import ContextManager
from pdsno.datastore import NIBStore
from pathlib import Path
import time

Path('./sim_phase6a').mkdir(exist_ok=True)
gc_context = ContextManager('./sim_phase6a/gc_context.yaml')
nib = NIBStore('./sim_phase6a/pdsno.db')

gc = GlobalController('global_cntl_1', gc_context, nib, enable_rest=True, rest_port=8001)
gc.start_rest_server_background()

print('GC running on http://localhost:8001')
while True: time.sleep(1)
"

# Terminal 2: Test health endpoint
curl http://localhost:8001/health
# Expected: {"status": "healthy", "controller_id": "global_cntl_1", ...}

curl http://localhost:8001/info
# Expected: {"controller_id": "global_cntl_1", "registered_handlers": [...], ...}
```

### Test 2: HTTP Validation Flow

```bash
# Run the multi-process simulation
python examples/simulate_rest_communication.py
```

**Expected output:**
```
[1/2] Starting Global Controller...
✓ Global Controller started on http://localhost:8001

[2/2] Starting Regional Controller...
✓ Regional Controller started on http://localhost:8002

[RC] Requesting validation from Global Controller...
[GC] Received VALIDATION_REQUEST from temp-rc-zone-a-001
[GC] Issued challenge challenge-xxx to temp-rc-zone-a-001
[RC] Received challenge challenge-xxx
[RC] Sending challenge response for challenge-xxx
[GC] Challenge verified successfully
[GC] ✓ Assigned identity: regional_cntl_zone-A_1
[RC] ✓ Validation successful! Assigned ID: regional_cntl_zone-A_1

Both controllers running. Press Ctrl+C to stop.
```

### Test 3: Manual HTTP Request

```bash
# With GC running, send a validation request manually
curl -X POST http://localhost:8001/message/validation_request \
  -H "Content-Type: application/json" \
  -d '{
    "message_id": "test-001",
    "message_type": "VALIDATION_REQUEST",
    "sender_id": "test-sender",
    "recipient_id": "global_cntl_1",
    "timestamp": "2026-02-22T00:00:00Z",
    "payload": {
      "temp_id": "test-sender",
      "controller_type": "regional",
      "region": "test-zone",
      "public_key": "test-key",
      "bootstrap_token": "test-token",
      "metadata": {}
    }
  }'
```

---

## Backwards Compatibility

Phase 6A maintains backwards compatibility with Phase 5:

**In-process mode (Phase 5):**
```python
# Create controllers without REST
gc = GlobalController("global_cntl_1", context, nib)
rc = RegionalController("temp-rc", "zone-A", context, nib, message_bus=bus)

# Use MessageBus
rc.request_validation("global_cntl_1")
```

**REST mode (Phase 6A):**
```python
# Create controllers with REST
gc = GlobalController("global_cntl_1", context, nib, enable_rest=True, rest_port=8001)
rc = RegionalController("temp-rc", "zone-A", context, nib, http_client=client, enable_rest=True, rest_port=8002)

# Start REST servers
gc.start_rest_server_background()
rc.start_rest_server_background()

# Use HTTP
rc.request_validation("global_cntl_1", "http://localhost:8001")
```

---

## Port Assignments

Standard port assignments for controllers:

| Controller Type | Port | URL |
|----------------|------|-----|
| Global Controller | 8001 | http://localhost:8001 |
| Regional Controller (zone-A) | 8002 | http://localhost:8002 |
| Regional Controller (zone-B) | 8003 | http://localhost:8003 |
| Local Controller 1 | 8100 | http://localhost:8100 |
| Local Controller 2 | 8101 | http://localhost:8101 |

---

## REST API Endpoints

Each controller exposes:

### Core Endpoints
- `GET /health` - Health check
- `GET /info` - Controller information

### Message Endpoints
- `POST /message/validation_request` - Handle validation requests
- `POST /message/challenge_response` - Handle challenge responses
- `POST /message/discovery_report` - Handle discovery reports
- etc. (one endpoint per message type the controller handles)

### Example Request Format
```json
{
  "message_id": "msg-abc123",
  "message_type": "VALIDATION_REQUEST",
  "sender_id": "sender_controller_id",
  "recipient_id": "recipient_controller_id",
  "timestamp": "2026-02-22T12:00:00Z",
  "payload": { ... },
  "correlation_id": "optional"
}
```

---

## Troubleshooting

### Issue: "Connection refused" errors

**Cause:** Target controller's REST server not running

**Fix:** Ensure you've called `start_rest_server_background()` on the controller

### Issue: "Recipient not in registry"

**Cause:** HTTP client doesn't know target controller's URL

**Fix:**
```python
http_client.register_controller("controller_id", "http://host:port")
```

### Issue: Port already in use

**Cause:** Previous controller process still running

**Fix:**
```bash
# Find and kill process
lsof -ti:8001 | xargs kill -9

# Or use different port
gc = GlobalController(..., rest_port=8011)
```

### Issue: Validation hangs

**Cause:** Controllers can't reach each other

**Fix:** Check firewall, ensure both controllers running, verify URLs

---

## Performance Considerations

### HTTP Overhead
- In-process MessageBus: ~0.001ms per message
- HTTP localhost: ~1-5ms per message
- HTTP network: ~10-50ms per message (depends on latency)

### When to Use REST vs MessageBus
- **Use MessageBus (Phase 5):** Testing, single-machine deployment, lowest latency
- **Use REST (Phase 6A):** Production, multi-machine, fault isolation, external integrations

---

## Next Steps

After Phase 6A is working:

**Phase 6B: MQTT for Pub/Sub**
- Add MQTT broker (Mosquitto)
- Pub/sub for discovery reports and policy updates
- Reduce point-to-point HTTP calls

**Phase 6C: Message Authentication**
- HMAC signatures on all messages
- Signature verification at endpoints
- Replay attack prevention

**Phase 6D: Multi-Machine Testing**
- Deploy GC on one machine
- Deploy RC on another
- Test cross-network validation

---

## Verification Checklist

- [ ] Dependencies installed
- [ ] New files copied to repo
- [ ] Global Controller updated with REST support
- [ ] Regional Controller updated with REST support
- [ ] Health check endpoints working
- [ ] Multi-process simulation runs successfully
- [ ] HTTP validation flow completes
- [ ] Backwards compatibility maintained (MessageBus still works)

Once complete:
✅ **Phase 6A Complete**

Ready for Phase 6B (MQTT) or Phase 6C (Message Authentication).
