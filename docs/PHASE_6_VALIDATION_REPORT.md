# Phase 6 Validation Report (REST + MQTT)

Date: February 23, 2026
Environment: Windows, Python 3.13.0, venv enabled
Workspace: Partially-Distributed-Smart-Network-Optimizer-PDSNO-

## Scope

Requested tasks:
1. Start Mosquitto broker (Docker)
2. Run MQTT simulation
3. Test REST endpoints manually
4. Verify cross-process communication

This report compiles actions taken, command outputs, and outcomes in a single document.

---

## 1) Docker - Mosquitto Broker

### Requirement
Start Mosquitto broker using Docker:

Command:
```
docker run -d -p 1883:1883 eclipse-mosquitto
```

### Result
Docker is not available in this environment.

Observed error:
```
docker : The term 'docker' is not recognized as the name of a cmdlet, function, script
file, or operable program.
```

### Notes
- Docker-specific assets must live under `docker/` per your instruction.
- A Docker Compose file was created under `docker/mosquitto/` for this purpose:
  - `docker/mosquitto/docker-compose.yml`

Compose file content:
```
version: "3.8"

services:
  mosquitto:
    image: eclipse-mosquitto:2
    container_name: pdsno-mosquitto
    ports:
      - "1883:1883"
    restart: unless-stopped
```

### Action Needed
Install Docker or run Mosquitto natively. After Docker is available, you can run either:

```
docker run -d -p 1883:1883 eclipse-mosquitto
```

or from the repo root:

```
docker compose -f docker/mosquitto/docker-compose.yml up -d
```

---

## 2) MQTT Simulation (Phase 6B)

### Command Used
```
python examples/simulate_mqtt_pubsub.py
```

### Environment Setup
- PYTHONPATH set to workspace root to allow `pdsno` imports.

### Output Summary
The simulation correctly detected that the broker is not running and exited.

Key output (abridged):
```
[1/6] Checking MQTT broker...
ERROR - MQTT broker not running on localhost:1883
Please start Mosquitto broker:
  Windows: mosquitto -v
  Docker: docker run -d -p 1883:1883 eclipse-mosquitto
```

### Result
MQTT simulation did not proceed because the broker was not running.

### Action Needed
Start Mosquitto (Docker or native), then rerun:

```
python examples/simulate_mqtt_pubsub.py
```

---

## 3) REST Simulation (Phase 6A) - Multi-process

### Command Used
```
python examples/simulate_rest_communication.py
```

### Pre-fix Issue
Windows encoding error occurred due to non-ASCII characters in subprocess scripts.

### Fix Applied
Updated `examples/simulate_rest_communication.py` to write subprocess scripts with UTF-8:

- `script_path.write_text(script, encoding="utf-8")` for both GC and RC scripts
- Removed non-ASCII characters from RC subprocess output message

### Result
After the fix, the simulation ran successfully with both controllers running and completing validation.

Observed milestones (abridged):
- Global Controller REST server started on port 8001
- Regional Controller REST server started on port 8002
- Validation flow executed over HTTP
- RC received challenge and returned response
- GC validated RC and assigned regional ID

---

## 4) Manual REST Endpoint Checks

The following commands were executed with `-UseBasicParsing` to avoid interactive prompts.

### Health Endpoints

Command:
```
Invoke-WebRequest http://localhost:8001/health -UseBasicParsing | Select-Object -ExpandProperty Content
```
Response:
```
{"status":"healthy","controller_id":"global_cntl_1","timestamp":"2026-02-23T10:50:32.531096+00:00"}
```

Command:
```
Invoke-WebRequest http://localhost:8002/health -UseBasicParsing | Select-Object -ExpandProperty Content
```
Response:
```
{"status":"healthy","controller_id":"regional_cntl_zone-A_1","timestamp":"2026-02-23T10:50:48.850624+00:00"}
```

### Info Endpoints

Command:
```
Invoke-WebRequest http://localhost:8001/info -UseBasicParsing | Select-Object -ExpandProperty Content
```
Response:
```
{"controller_id":"global_cntl_1","registered_handlers":["VALIDATION_REQUEST","CHALLENGE_RESPONSE"],"host":"127.0.0.1","port":8001}
```

Command:
```
Invoke-WebRequest http://localhost:8002/info -UseBasicParsing | Select-Object -ExpandProperty Content
```
Response:
```
{"controller_id":"regional_cntl_zone-A_1","registered_handlers":["DISCOVERY_REPORT"],"host":"127.0.0.1","port":8002}
```

### Result
Manual REST endpoint checks succeeded for both GC and RC.

---

## 5) Cross-Process Communication Verification

The REST simulation log confirms that cross-process communication works as expected:

Evidence observed in output:
- GC registered handlers for VALIDATION_REQUEST and CHALLENGE_RESPONSE
- RC registered handler for DISCOVERY_REPORT
- RC sent VALIDATION_REQUEST to GC
- GC issued CHALLENGE to RC
- RC responded with CHALLENGE_RESPONSE
- GC verified and assigned identity
- RC updated REST server ID

### Result
Cross-process REST communication validated successfully.

---

## Status Summary

- Docker Mosquitto broker: Not started (Docker not available)
- MQTT simulation: Blocked by missing broker
- REST multi-process simulation: Successful
- Manual REST checks: Successful
- Cross-process validation: Successful

---

## Next Actions (If You Want Full MQTT Validation)

1) Install Docker or Mosquitto
2) Start the broker:
```
docker run -d -p 1883:1883 eclipse-mosquitto
```
3) Rerun MQTT simulation:
```
python examples/simulate_mqtt_pubsub.py
```

---

## Notes on File Locations

- Docker assets: `docker/mosquitto/docker-compose.yml`
- REST simulation: `examples/simulate_rest_communication.py`
- MQTT simulation: `examples/simulate_mqtt_pubsub.py`

End of report.
