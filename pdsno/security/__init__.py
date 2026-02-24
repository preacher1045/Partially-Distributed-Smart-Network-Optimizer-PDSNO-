"""
PDSNO Security Module

Comprehensive security infrastructure:
- Authentication (controllers, operators, API clients, devices)
- Authorization (role-based access control)
- Secret management (encrypted storage)
- Message authentication (HMAC signatures)
- Key distribution (Diffie-Hellman)
"""

# Message authentication (Phase 6C)
from pdsno.security.message_auth import (
    MessageAuthenticator,
    KeyManager
)

# Key distribution (Phase 6D)
from pdsno.security.key_distribution import (
    DHKeyExchange,
    KeyDistributionProtocol,
    KeyRotationScheduler
)

# Authentication (Phase 7+)
from pdsno.security.auth import (
    EntityType,
    AuthenticationResult,
    ControllerAuthenticator,
    APIClientAuthenticator,
    OperatorAuthenticator,
    DeviceAuthenticator
)

# Authorization (Phase 7+)
from pdsno.security.rbac import (
    Role,
    Resource,
    Action,
    Permission,
    RoleDefinition,
    RBACManager
)

# Secret Management (Phase 7+)
from pdsno.security.secret_manager import (
    SecretType,
    SecretMetadata,
    SecretManager,
    ExternalKMSAdapter
)

__all__ = [
    # Message Auth
    'MessageAuthenticator',
    'KeyManager',
    
    # Key Distribution
    'DHKeyExchange',
    'KeyDistributionProtocol',
    'KeyRotationScheduler',
    
    # Authentication
    'EntityType',
    'AuthenticationResult',
    'ControllerAuthenticator',
    'APIClientAuthenticator',
    'OperatorAuthenticator',
    'DeviceAuthenticator',
    
    # Authorization
    'Role',
    'Resource',
    'Action',
    'Permission',
    'RoleDefinition',
    'RBACManager',
    
    # Secret Management
    'SecretType',
    'SecretMetadata',
    'SecretManager',
    'ExternalKMSAdapter'
]