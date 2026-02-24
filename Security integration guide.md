# PDSNO Security Components - Complete Guide

## Overview

The PDSNO security module provides comprehensive authentication, authorization, and secret management:

### **auth.py** - Multi-Entity Authentication
Handles authentication for 4 entity types:
1. **Controllers** (system-to-system via challenge-response)
2. **API Clients** (external systems via API keys)
3. **Operators** (humans via username/password + MFA)
4. **Devices** (network equipment via credentials)

### **rbac.py** - Role-Based Access Control
Manages permissions for:
- 10 predefined roles (Global Controller, Regional Admin, etc.)
- 10 resource types (configs, devices, audit logs, etc.)
- 9 action types (create, read, approve, execute, etc.)

### **secret_manager.py** - Secure Secret Storage
Handles:
- Encrypted storage (AES-256-GCM)
- Secret rotation
- Expiration tracking
- External KMS integration (AWS, Vault, Azure)

---

## What We're Authenticating & Why

### 1. **Controllers** (System-to-System)
**What:** Regional/Local controllers joining the network  
**Why:** Prevent rogue controllers from infiltrating the system  
**Method:** Bootstrap token + challenge-response (existing validation flow)  
**Used By:** Global Controller validating Regional, Regional validating Local

**Example:**
```python
from pdsno.security import ControllerAuthenticator

# On Global Controller
controller_auth = ControllerAuthenticator(bootstrap_secret=b'...')

# Step 1: Verify bootstrap token
valid, error = controller_auth.verify_bootstrap_token(
    temp_id="temp-rc-001",
    region="zone-A",
    controller_type="regional",
    submitted_token="abc123..."
)

# Step 2: Issue challenge
challenge = controller_auth.issue_challenge("temp-rc-001", public_key="...")

# Step 3: Verify response
valid, error = controller_auth.verify_challenge_response(
    challenge_id=challenge['challenge_id'],
    signed_nonce="signed_data...",
    responder_temp_id="temp-rc-001"
)
```

---

### 2. **API Clients** (External Systems)
**What:** Monitoring systems, orchestration platforms accessing PDSNO APIs  
**Why:** Control external access to network data and operations  
**Method:** API key authentication with rate limiting  
**Used By:** REST API endpoints

**Example:**
```python
from pdsno.security import APIClientAuthenticator, SecretManager

secret_mgr = SecretManager()
api_auth = APIClientAuthenticator(secret_mgr)

# Generate API key for monitoring system
api_key = api_auth.generate_api_key(
    client_name="prometheus",
    permissions=["read:devices", "read:audit"],
    rate_limit_per_hour=10000
)
# Returns: "pdsno_xyzabc123..."

# On each API request, verify key
result = api_auth.verify_api_key(api_key)
if result.success:
    # Check permissions
    permissions = result.metadata['permissions']
    if 'read:devices' in permissions:
        # Allow access
        pass
```

---

### 3. **Operators** (Humans)
**What:** Network admins approving configs, viewing audit logs  
**Why:** Ensure only authorized personnel can approve HIGH configs  
**Method:** Username/password + MFA (TOTP)  
**Used By:** Web UI, CLI tools

**Example:**
```python
from pdsno.security import OperatorAuthenticator, SecretManager

secret_mgr = SecretManager()
operator_auth = OperatorAuthenticator(secret_mgr)

# Create admin account
operator_auth.create_user(
    username="alice",
    password="SecurePass123!",
    role="global_admin",
    mfa_enabled=True
)

# Login with MFA
result = operator_auth.authenticate(
    username="alice",
    password="SecurePass123!",
    mfa_code="123456"  # From authenticator app
)

if result.success:
    session_token = result.session_token
    # Use token for subsequent requests
    
    # Later, verify session
    session_result = operator_auth.verify_session(session_token)
```

---

### 4. **Devices** (Network Equipment)
**What:** Switches/routers being configured by PDSNO  
**Why:** Securely store credentials for device management  
**Method:** Encrypted credential storage  
**Used By:** Local Controllers applying configurations

**Example:**
```python
from pdsno.security import DeviceAuthenticator, SecretManager

secret_mgr = SecretManager()
device_auth = DeviceAuthenticator(secret_mgr)

# Register device credentials
device_auth.register_device(
    device_id="switch-core-01",
    username="admin",
    password="switch_password",
    protocol="ssh"
)

# When connecting to device
creds = device_auth.get_device_credentials("switch-core-01")
# Use creds['username'] and creds['password'] to SSH
```

---

## Role-Based Access Control (RBAC)

### Predefined Roles

| Role | Can Do |
|------|--------|
| **Global Controller** | Validate RCs, approve HIGH configs, issue tokens |
| **Regional Controller** | Validate LCs, approve MEDIUM configs, manage region |
| **Local Controller** | Create configs, auto-approve LOW, execute with token |
| **Global Admin** (human) | Everything |
| **Regional Admin** (human) | Approve MEDIUM, manage region devices |
| **Local Operator** (human) | Create LOW configs, view devices |
| **Viewer** (human) | Read-only access |
| **API Client** | Create/read configs via API |
| **API Client Read-Only** | Read-only via API |

### Permission Checks

```python
from pdsno.security import RBACManager, Role, Resource, Action

rbac = RBACManager()

# Assign roles
rbac.assign_role("global_cntl_1", Role.GLOBAL_CONTROLLER)
rbac.assign_role("alice", Role.GLOBAL_ADMIN)
rbac.assign_role("monitoring_api", Role.API_CLIENT_READONLY)

# Check permissions

# Can Global Controller approve HIGH config?
can_approve = rbac.check_permission(
    entity_id="global_cntl_1",
    resource=Resource.CONFIG,
    action=Action.APPROVE,
    context={'sensitivity': 'HIGH'}
)  # True

# Can Regional Controller approve HIGH config?
can_approve = rbac.check_permission(
    entity_id="regional_cntl_zone-A_1",
    resource=Resource.CONFIG,
    action=Action.APPROVE,
    context={'sensitivity': 'HIGH'}
)  # False - only MEDIUM and LOW

# Can monitoring API create configs?
can_create = rbac.check_permission(
    entity_id="monitoring_api",
    resource=Resource.CONFIG,
    action=Action.CREATE
)  # False - read-only
```

---

## Secret Management

### Storing Secrets

```python
from pdsno.security import SecretManager, SecretType

secret_mgr = SecretManager(master_key=b'...')  # 32 bytes

# Store different secret types

# 1. API Keys
secret_mgr.store_secret(
    secret_id="prometheus_api_key",
    secret_value=b"pdsno_abc123xyz",
    secret_type=SecretType.API_KEY,
    rotation_policy_days=90,
    metadata={'client': 'prometheus'}
)

# 2. Device Passwords
secret_mgr.store_secret(
    secret_id="device_switch01_password",
    secret_value=b"switch_pass",
    secret_type=SecretType.DEVICE_PASSWORD,
    metadata={'device_id': 'switch-01', 'protocol': 'ssh'}
)

# 3. Bootstrap Tokens
secret_mgr.store_secret(
    secret_id="bootstrap_zone_A",
    secret_value=b"token_abc123",
    secret_type=SecretType.BOOTSTRAP_TOKEN,
    rotation_policy_days=30
)
```

### Retrieving Secrets

```python
# Retrieve and decrypt
api_key_bytes = secret_mgr.retrieve_secret("prometheus_api_key")
if api_key_bytes:
    api_key = api_key_bytes.decode()

# Check what needs rotation
needs_rotation = secret_mgr.check_rotation_needed()
for secret_id in needs_rotation:
    print(f"Rotate: {secret_id}")

# Rotate secret
new_value = secrets.token_bytes(32)
secret_mgr.rotate_secret("bootstrap_zone_A", new_value)
```

### External KMS Integration

```python
from pdsno.security import ExternalKMSAdapter

# AWS Secrets Manager
aws_kms = ExternalKMSAdapter(
    kms_type="aws",
    config={'region': 'us-west-2'}
)

aws_kms.store_secret("pdsno/device/switch01", "password123")
password = aws_kms.retrieve_secret("pdsno/device/switch01")

# HashiCorp Vault
vault_kms = ExternalKMSAdapter(
    kms_type="vault",
    config={
        'url': 'https://vault.example.com',
        'token': 'hvs.xxx'
    }
)

vault_kms.store_secret("pdsno/bootstrap/zone-A", "token_xyz")
```

---

## Integration with Existing Components

### 1. Controller Validation (Phase 4)

**Update `global_controller.py`:**
```python
from pdsno.security import ControllerAuthenticator, RBACManager, Role

class GlobalController(BaseController):
    def __init__(self, ...):
        # ... existing init ...
        
        # Add authentication
        self.controller_auth = ControllerAuthenticator(bootstrap_secret=...)
        
        # Add RBAC
        self.rbac = RBACManager()
        self.rbac.assign_role(self.controller_id, Role.GLOBAL_CONTROLLER)
    
    def handle_validation_request(self, envelope):
        # Step 1: Verify bootstrap token
        valid, error = self.controller_auth.verify_bootstrap_token(...)
        
        # Step 2: Issue challenge
        challenge = self.controller_auth.issue_challenge(...)
        
        # ... rest of validation flow
```

### 2. Config Approval (Phase 7)

**Update `approval_engine.py`:**
```python
from pdsno.security import RBACManager, Resource, Action

class ApprovalWorkflowEngine:
    def __init__(self, ...):
        # ... existing init ...
        self.rbac = RBACManager()
    
    def approve_request(self, request_id, approver_id):
        # Check RBAC permission
        request = self.requests[request_id]
        
        can_approve = self.rbac.check_permission(
            entity_id=approver_id,
            resource=Resource.CONFIG,
            action=Action.APPROVE,
            context={'sensitivity': request.sensitivity.value}
        )
        
        if not can_approve:
            return False  # Not authorized
        
        # ... rest of approval logic
```

### 3. REST API Authentication

**Add to REST endpoints:**
```python
from pdsno.security import APIClientAuthenticator, RBACManager

api_auth = APIClientAuthenticator(secret_mgr)
rbac = RBACManager()

@app.get("/devices")
def get_devices(api_key: str = Header(...)):
    # Authenticate
    result = api_auth.verify_api_key(api_key)
    
    if not result.success:
        raise HTTPException(401, "Invalid API key")
    
    # Authorize
    can_read = rbac.check_permission(
        entity_id=result.entity_id,
        resource=Resource.DEVICE,
        action=Action.READ
    )
    
    if not can_read:
        raise HTTPException(403, "Insufficient permissions")
    
    # Return devices...
```

---

## Dependencies

Add to `requirements.txt`:
```
cryptography>=42.0.0
PyJWT>=2.8.0
bcrypt>=4.1.0
pyotp>=2.9.0
boto3>=1.34.0  # Optional: for AWS KMS
hvac>=2.1.0    # Optional: for Vault
```

---

## Security Best Practices

### 1. Master Key Management
```python
# ❌ DON'T: Hardcode master key
secret_mgr = SecretManager(master_key=b'hardcoded_key')

# ✅ DO: Load from environment or KMS
import os
master_key = os.environ.get('PDSNO_MASTER_KEY').encode()
secret_mgr = SecretManager(master_key=master_key)
```

### 2. Secret Rotation
```python
# Schedule regular rotation checks
import schedule

def rotate_secrets():
    needs_rotation = secret_mgr.check_rotation_needed()
    for secret_id in needs_rotation:
        # Generate new secret
        new_value = generate_new_secret(secret_id)
        secret_mgr.rotate_secret(secret_id, new_value)

schedule.every().day.at("03:00").do(rotate_secrets)
```

### 3. Audit Logging
```python
from pdsno.config import AuditTrail

audit = AuditTrail("security_audit")

# Log authentication attempts
result = operator_auth.authenticate(username, password, mfa)
if result.success:
    audit.log_event(..., action="login", result="SUCCESS")
else:
    audit.log_event(..., action="login", result="FAILURE")
```

---

## Files to Update

1. **`pdsno/security/auth.py`** - Authentication (new)
2. **`pdsno/security/rbac.py`** - Authorization (new)
3. **`pdsno/security/secret_manager.py`** - Secret storage (new)
4. **`pdsno/security/__init__.py`** - Module exports (updated)
5. **`pdsno/controllers/global_controller.py`** - Add controller auth
6. **`pdsno/controllers/regional_controller.py`** - Add controller auth
7. **`pdsno/config/approval_engine.py`** - Add RBAC checks
8. **`pdsno/communication/rest_server.py`** - Add API authentication
9. **`requirements.txt`** - Add dependencies

---

## Testing

Create `tests/test_security.py`:
```python
def test_controller_authentication():
    auth = ControllerAuthenticator(b'x' * 32)
    valid, _ = auth.verify_bootstrap_token(...)
    assert valid

def test_rbac_permissions():
    rbac = RBACManager()
    rbac.assign_role("gc", Role.GLOBAL_CONTROLLER)
    can_approve = rbac.can_approve_config("gc", "HIGH")
    assert can_approve

def test_secret_encryption():
    mgr = SecretManager()
    mgr.store_secret("test", b"secret_data", SecretType.API_KEY)
    retrieved = mgr.retrieve_secret("test")
    assert retrieved == b"secret_data"
```

---

## Summary

**What Each Component Does:**

| Component | Purpose | Used For |
|-----------|---------|----------|
| **auth.py** | Who can access? | Controller validation, API access, operator login |
| **rbac.py** | What can they do? | Permission checks before config approval/execution |
| **secret_manager.py** | Where are secrets stored? | Device passwords, API keys, bootstrap tokens |

**Integration Points:**
- Controller validation → `auth.py` (bootstrap token + challenge)
- Config approval → `rbac.py` (check if can approve HIGH/MEDIUM/LOW)
- Device connection → `secret_manager.py` (retrieve device credentials)
- API access → `auth.py` + `rbac.py` (verify key + check permissions)
- Operator actions → `auth.py` (login) + `rbac.py` (authorize action)

---

**Ready for integration!**