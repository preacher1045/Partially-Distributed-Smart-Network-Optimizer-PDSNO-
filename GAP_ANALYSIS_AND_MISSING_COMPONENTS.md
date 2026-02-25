# PDSNO - Complete Gap Analysis & Missing Components

## Executive Summary

**Current Status:** ~95% complete on paper, but **missing critical operational scripts** and **vendor abstraction layer**

**What Exists:**
- ✅ Core framework (controllers, NIB, algorithms)
- ✅ Communication layer (REST, MQTT, message auth)
- ✅ Security (auth, RBAC, secrets, key distribution)
- ✅ Configuration approval (workflows, tokens, rollback)
- ✅ Test suite and examples
- ✅ Comprehensive documentation

**What's Missing:**
- ❌ Operational/deployment scripts (run_controller.py, init_db.py, etc.)
- ❌ Vendor abstraction layer (Cisco/Juniper/Arista adapters)
- ❌ CLI interface for operations
- ❌ Device connection management
- ❌ Real device integration examples

---

## Part 1: Missing Scripts Directory

### Current State
The `examples/` directory has:
- ✅ `basic_algorithm_usage.py` - Algorithm demonstration
- ✅ `nib_store_usage.py` - NIB operations
- ✅ `simulate_validation.py` - Controller validation
- ✅ `simulate_discovery.py` - Device discovery
- ❌ **NO operational deployment scripts**

### Critical Missing Scripts

#### 1. `scripts/run_controller.py` ❌
**Purpose:** Main entry point to run any controller type

**What It Should Do:**
```python
#!/usr/bin/env python3
"""
PDSNO Controller Runner

Start Global, Regional, or Local Controller with proper configuration.

Usage:
    # Global Controller
    python scripts/run_controller.py --type global --port 8001
    
    # Regional Controller
    python scripts/run_controller.py --type regional --region zone-A --parent global_cntl_1
    
    # Local Controller
    python scripts/run_controller.py --type local --region zone-A --parent regional_cntl_zone-A_1
"""

import argparse
import logging
from pathlib import Path

from pdsno.controllers.global_controller import GlobalController
from pdsno.controllers.regional_controller import RegionalController
from pdsno.controllers.local_controller import LocalController
from pdsno.controllers.context_manager import ContextManager
from pdsno.datastore import NIBStore


def parse_args():
    parser = argparse.ArgumentParser(description='PDSNO Controller Runner')
    
    parser.add_argument('--type', required=True, choices=['global', 'regional', 'local'],
                       help='Controller type')
    parser.add_argument('--region', help='Region name (for regional/local)')
    parser.add_argument('--parent', help='Parent controller ID')
    parser.add_argument('--port', type=int, default=8001, help='REST API port')
    parser.add_argument('--mqtt-broker', default='localhost', help='MQTT broker host')
    parser.add_argument('--config', default='config/context_runtime.yaml',
                       help='Context configuration file')
    parser.add_argument('--db', default='config/pdsno.db', help='NIB database path')
    parser.add_argument('--enable-tls', action='store_true', help='Enable TLS')
    parser.add_argument('--cert', help='TLS certificate path')
    parser.add_argument('--key', help='TLS key path')
    
    return parser.parse_args()


def main():
    args = parse_args()
    
    # Initialize infrastructure
    context_mgr = ContextManager(args.config)
    nib_store = NIBStore(args.db)
    
    # Create appropriate controller
    if args.type == 'global':
        controller = GlobalController(
            controller_id="global_cntl_1",
            context_manager=context_mgr,
            nib_store=nib_store,
            rest_port=args.port,
            enable_rest=True,
            enable_tls=args.enable_tls,
            cert_file=args.cert,
            key_file=args.key
        )
    
    elif args.type == 'regional':
        if not args.region or not args.parent:
            raise ValueError("Regional controller requires --region and --parent")
        
        controller = RegionalController(
            temp_id=f"temp-rc-{args.region}",
            region=args.region,
            context_manager=context_mgr,
            nib_store=nib_store,
            enable_rest=True,
            rest_port=args.port
        )
        
        # Request validation from parent
        controller.request_validation(args.parent)
    
    elif args.type == 'local':
        if not args.region or not args.parent:
            raise ValueError("Local controller requires --region and --parent")
        
        controller = LocalController(
            temp_id=f"temp-lc-{args.region}",
            region=args.region,
            context_manager=context_mgr,
            nib_store=nib_store
        )
        
        # Request validation
        controller.request_validation(args.parent)
    
    # Start controller
    print(f"\nStarting {args.type.upper()} Controller...")
    print(f"Region: {args.region or 'N/A'}")
    print(f"REST API: http{'s' if args.enable_tls else ''}://0.0.0.0:{args.port}")
    print(f"MQTT Broker: {args.mqtt_broker}")
    print("\nPress Ctrl+C to stop\n")
    
    try:
        controller.run()
    except KeyboardInterrupt:
        print("\n\nShutting down gracefully...")
        controller.shutdown()


if __name__ == "__main__":
    main()
```

#### 2. `scripts/init_db.py` ❌
**Purpose:** Initialize NIB database schema

```python
#!/usr/bin/env python3
"""
Initialize PDSNO Database

Creates the NIB schema and optional seed data.

Usage:
    python scripts/init_db.py --db config/pdsno.db
    python scripts/init_db.py --db config/pdsno.db --seed-data
"""

import argparse
from pdsno.datastore import NIBStore

def main():
    parser = argparse.ArgumentParser(description='Initialize PDSNO Database')
    parser.add_argument('--db', default='config/pdsno.db', help='Database path')
    parser.add_argument('--seed-data', action='store_true', help='Add seed data')
    parser.add_argument('--drop-existing', action='store_true', help='Drop existing tables')
    
    args = parser.parse_args()
    
    print(f"Initializing database: {args.db}")
    
    if args.drop_existing:
        print("⚠️  Dropping existing tables...")
        # Drop logic here
    
    # Create NIBStore (auto-creates schema)
    nib = NIBStore(args.db)
    
    print("✓ Database schema created")
    
    if args.seed_data:
        print("Adding seed data...")
        # Add sample devices, controllers, etc.
        print("✓ Seed data added")
    
    print("\nDatabase ready!")


if __name__ == "__main__":
    main()
```

#### 3. `scripts/generate_bootstrap_token.py` ❌
**Purpose:** Generate bootstrap tokens for controller provisioning

```python
#!/usr/bin/env python3
"""
Generate Bootstrap Token

Creates HMAC-signed bootstrap tokens for controller validation.

Usage:
    python scripts/generate_bootstrap_token.py --region zone-A --type regional
"""

import argparse
import hmac
import hashlib
import secrets

def main():
    parser = argparse.ArgumentParser(description='Generate Bootstrap Token')
    parser.add_argument('--region', required=True, help='Region name')
    parser.add_argument('--type', required=True, choices=['regional', 'local'],
                       help='Controller type')
    parser.add_argument('--secret-file', default='config/bootstrap_secret.key',
                       help='Bootstrap secret file')
    
    args = parser.parse_args()
    
    # Load or generate secret
    try:
        with open(args.secret_file, 'rb') as f:
            secret = f.read()
    except FileNotFoundError:
        print(f"Generating new bootstrap secret...")
        secret = secrets.token_bytes(32)
        with open(args.secret_file, 'wb') as f:
            f.write(secret)
        print(f"✓ Secret saved to {args.secret_file}")
    
    # Generate temp ID
    temp_id = f"temp-{args.type[:2]}-{args.region}-{secrets.token_hex(4)}"
    
    # Generate token
    token_input = f"{temp_id}|{args.region}|{args.type}".encode()
    token = hmac.new(secret, token_input, hashlib.sha256).hexdigest()
    
    print("\n" + "="*60)
    print("Bootstrap Token Generated")
    print("="*60)
    print(f"Temp ID:   {temp_id}")
    print(f"Region:    {args.region}")
    print(f"Type:      {args.type}")
    print(f"Token:     {token}")
    print("="*60)
    print("\nUse these values when starting the controller")


if __name__ == "__main__":
    main()
```

#### 4. `scripts/deploy.sh` ❌
**Purpose:** Deployment automation script

```bash
#!/bin/bash
# PDSNO Deployment Script

set -e

echo "PDSNO Deployment"
echo "================"

# Check Python version
python --version

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Initialize database
echo "Initializing database..."
python scripts/init_db.py --db /opt/pdsno/data/pdsno.db

# Generate certificates (if not exist)
if [ ! -f /etc/pdsno/certs/controller-cert.pem ]; then
    echo "Generating TLS certificates..."
    bash scripts/generate_certs.sh
fi

# Create systemd service
echo "Creating systemd service..."
sudo cp deployment/pdsno-controller.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pdsno-controller

echo "✓ Deployment complete!"
echo "Start controller with: sudo systemctl start pdsno-controller"
```

#### 5. `scripts/health_check.py` ❌
**Purpose:** Check system health

```python
#!/usr/bin/env python3
"""
PDSNO Health Check

Verify all components are operational.

Usage:
    python scripts/health_check.py --url http://localhost:8001
"""

import argparse
import requests
import sys

def main():
    parser = argparse.ArgumentParser(description='PDSNO Health Check')
    parser.add_argument('--url', default='http://localhost:8001',
                       help='Controller URL')
    
    args = parser.parse_args()
    
    try:
        # Check health endpoint
        response = requests.get(f"{args.url}/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Controller: {data['status']}")
            print(f"✓ Version: {data.get('version', 'unknown')}")
            sys.exit(0)
        else:
            print(f"✗ Health check failed: {response.status_code}")
            sys.exit(1)
    
    except requests.exceptions.RequestException as e:
        print(f"✗ Cannot connect to controller: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

---

## Part 2: Missing Vendor Abstraction Layer

### Current State
**EXISTS:** Generic intent models in docs
**MISSING:** Actual implementation

### Required Components

#### 1. `pdsno/adapters/__init__.py` ❌
**Purpose:** Vendor adapter module

#### 2. `pdsno/adapters/base_adapter.py` ❌
**Purpose:** Base adapter interface

```python
from abc import ABC, abstractmethod
from typing import Dict, List
from pdsno.config.config_state import ConfigIntent

class VendorAdapter(ABC):
    """Base class for all vendor adapters"""
    
    @abstractmethod
    def connect(self, device_info: Dict) -> bool:
        """Connect to device"""
        pass
    
    @abstractmethod
    def translate_intent(self, intent: ConfigIntent) -> List[str]:
        """Translate generic intent to vendor commands"""
        pass
    
    @abstractmethod
    def apply_config(self, commands: List[str]) -> Dict:
        """Apply configuration"""
        pass
    
    @abstractmethod
    def get_config(self) -> str:
        """Get running configuration"""
        pass
    
    @abstractmethod
    def verify_config(self, intent: ConfigIntent) -> bool:
        """Verify configuration was applied"""
        pass
```

#### 3. `pdsno/adapters/cisco_ios_adapter.py` ❌
**Purpose:** Cisco IOS/IOS-XE adapter

#### 4. `pdsno/adapters/juniper_adapter.py` ❌
**Purpose:** Juniper JunOS adapter

#### 5. `pdsno/adapters/arista_adapter.py` ❌
**Purpose:** Arista EOS adapter

#### 6. `pdsno/adapters/netconf_adapter.py` ❌
**Purpose:** Generic NETCONF adapter

#### 7. `pdsno/adapters/factory.py` ❌
**Purpose:** Adapter factory

```python
class VendorAdapterFactory:
    """Create appropriate adapter for device"""
    
    ADAPTERS = {
        ('cisco', 'ios'): CiscoIOSAdapter,
        ('juniper', 'junos'): JuniperAdapter,
        ('arista', 'eos'): AristaAdapter,
        ('netconf', 'generic'): NETCONFAdapter,
    }
    
    @classmethod
    def create_adapter(cls, device: Dict) -> VendorAdapter:
        vendor = device.get('vendor', '').lower()
        platform = device.get('platform', '').lower()
        
        adapter_class = cls.ADAPTERS.get((vendor, platform))
        if not adapter_class:
            raise ValueError(f"No adapter for {vendor}/{platform}")
        
        return adapter_class(device)
```

---

## Part 3: Missing CLI Interface

### Current State
**EXISTS:** `pdsno/main.py` (placeholder only)
**MISSING:** Full CLI with commands

### Required CLI Commands

```
pdsno
├── controller (start, stop, status)
├── device (add, list, remove, scan)
├── config (create, approve, execute, rollback)
├── validation (request, status)
├── db (init, migrate, backup, restore)
├── token (generate, verify, list)
└── health (check, metrics, logs)
```

---

## Part 4: Missing Device Connection Management

### Current State
**EXISTS:** Discovery algorithms (ARP, ICMP, SNMP)
**MISSING:** Actual device connection and session management

### Required Components

#### 1. `pdsno/devices/connection_manager.py` ❌
**Purpose:** Manage persistent connections to devices

```python
class ConnectionManager:
    """Manage device connections"""
    
    def __init__(self, secret_manager):
        self.connections = {}  # device_id -> connection
        self.secret_manager = secret_manager
    
    def connect(self, device_id: str) -> Connection:
        """Establish connection to device"""
        pass
    
    def disconnect(self, device_id: str):
        """Close connection"""
        pass
    
    def execute(self, device_id: str, commands: List[str]) -> Dict:
        """Execute commands on device"""
        pass
```

#### 2. `pdsno/devices/session.py` ❌
**Purpose:** Device session abstraction

---

## Part 5: Production Deployment Gaps

### Missing Files

1. **`deployment/systemd/pdsno-controller.service`** ❌
2. **`deployment/docker/Dockerfile`** ❌
3. **`deployment/docker/docker-compose.yml`** ❌
4. **`deployment/kubernetes/controller-deployment.yaml`** ❌
5. **`deployment/ansible/playbook.yml`** ❌

### Missing Configuration Templates

1. **`config/context_runtime.yaml.template`** ❌
2. **`config/policy_default.yaml.template`** ❌
3. **`.env.example`** ❌

---

## Priority Implementation Plan

### Phase 1: Operational Scripts (HIGHEST PRIORITY)
**Time:** 4-6 hours

1. ✅ Create `scripts/` directory
2. ✅ Implement `run_controller.py` 
3. ✅ Implement `init_db.py`
4. ✅ Implement `generate_bootstrap_token.py`
5. ✅ Create deployment scripts

### Phase 2: Vendor Abstraction Layer (HIGH PRIORITY)
**Time:** 8-12 hours

1. ✅ Create `pdsno/adapters/` module
2. ✅ Implement base adapter interface
3. ✅ Implement Cisco adapter (most common)
4. ✅ Implement NETCONF adapter (vendor-agnostic)
5. ✅ Create adapter factory
6. ✅ Add adapter tests

### Phase 3: CLI Interface (MEDIUM PRIORITY)
**Time:** 6-8 hours

1. ✅ Replace placeholder `main.py`
2. ✅ Implement Click-based CLI
3. ✅ Add all essential commands
4. ✅ Add command help and documentation

### Phase 4: Device Connection Management (MEDIUM PRIORITY)
**Time:** 4-6 hours

1. ✅ Implement ConnectionManager
2. ✅ Add session pooling
3. ✅ Add connection health checks
4. ✅ Integrate with adapters

### Phase 5: Production Deployment (LOW PRIORITY - POLISH)
**Time:** 4-6 hours

1. ✅ Create systemd service files
2. ✅ Create Docker/K8s manifests
3. ✅ Create Ansible playbooks
4. ✅ Add configuration templates

---

## Complete Gap Checklist

### Scripts & Operations
- [ ] `scripts/run_controller.py`
- [ ] `scripts/init_db.py`
- [ ] `scripts/generate_bootstrap_token.py`
- [ ] `scripts/deploy.sh`
- [ ] `scripts/health_check.py`
- [ ] `scripts/generate_certs.sh`

### Vendor Abstraction
- [ ] `pdsno/adapters/__init__.py`
- [ ] `pdsno/adapters/base_adapter.py`
- [ ] `pdsno/adapters/cisco_ios_adapter.py`
- [ ] `pdsno/adapters/juniper_adapter.py`
- [ ] `pdsno/adapters/arista_adapter.py`
- [ ] `pdsno/adapters/netconf_adapter.py`
- [ ] `pdsno/adapters/factory.py`
- [ ] Integration with LocalController

### CLI Interface
- [ ] Full `pdsno/main.py` replacement
- [ ] Click command structure
- [ ] All essential commands
- [ ] Help documentation

### Device Management
- [ ] `pdsno/devices/connection_manager.py`
- [ ] `pdsno/devices/session.py`
- [ ] Integration with adapters
- [ ] Session pooling

### Deployment
- [ ] `deployment/systemd/pdsno-controller.service`
- [ ] `deployment/docker/Dockerfile`
- [ ] `deployment/docker/docker-compose.yml`
- [ ] `deployment/kubernetes/*.yaml`
- [ ] `deployment/ansible/playbook.yml`

### Configuration
- [ ] `config/context_runtime.yaml.template`
- [ ] `config/policy_default.yaml.template`
- [ ] `.env.example`

---

## Immediate Next Steps

**START HERE:**
1. Create operational scripts (Phase 1)
2. Implement vendor adapters (Phase 2)
3. Build CLI interface (Phase 3)

This will make PDSNO **fully operational and production-ready**.
