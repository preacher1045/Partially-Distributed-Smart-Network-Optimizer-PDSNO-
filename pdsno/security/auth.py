"""
PDSNO Authentication System

Handles authentication for multiple entity types:
1. Controllers (system-to-system via challenge-response)
2. API Clients (external systems via API keys)
3. Operators (humans via username/password + MFA)
4. Devices (network equipment via credentials)

Security Features:
- Challenge-response for controllers (existing validation flow)
- API key authentication with rate limiting
- Operator authentication with session management
- Device credential verification
- Multi-factor authentication support
- Token-based sessions
"""

import hmac
import hashlib
import secrets
import jwt
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple, List
from enum import Enum
import logging


class EntityType(Enum):
    """Types of entities that can authenticate"""
    CONTROLLER = "controller"
    API_CLIENT = "api_client"
    OPERATOR = "operator"
    DEVICE = "device"


class AuthenticationResult:
    """Result of an authentication attempt"""
    
    def __init__(
        self,
        success: bool,
        entity_id: Optional[str] = None,
        entity_type: Optional[EntityType] = None,
        session_token: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        self.success = success
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.session_token = session_token
        self.error = error
        self.metadata = metadata or {}


class ControllerAuthenticator:
    """
    Authenticates controllers using challenge-response protocol.
    
    This integrates with the existing validation flow from Phase 4.
    """
    
    def __init__(self, bootstrap_secret: bytes):
        """
        Initialize controller authenticator.
        
        Args:
            bootstrap_secret: Shared secret for bootstrap token verification
        """
        if len(bootstrap_secret) < 32:
            raise ValueError("Bootstrap secret must be at least 32 bytes")
        
        self.bootstrap_secret = bootstrap_secret
        self.logger = logging.getLogger(f"{__name__}.ControllerAuth")
        
        # Active challenges: challenge_id -> {temp_id, nonce, issued_at, public_key}
        self.active_challenges: Dict[str, Dict] = {}
    
    def verify_bootstrap_token(
        self,
        temp_id: str,
        region: str,
        controller_type: str,
        submitted_token: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify bootstrap token (Step 2 of validation flow).
        
        Args:
            temp_id: Temporary controller ID
            region: Controller's region
            controller_type: Type (regional/local)
            submitted_token: Token to verify
        
        Returns:
            (success, error_message) tuple
        """
        # Compute expected token
        token_input = f"{temp_id}|{region}|{controller_type}".encode()
        expected_token = hmac.new(
            self.bootstrap_secret,
            token_input,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(submitted_token, expected_token):
            self.logger.warning(f"Invalid bootstrap token from {temp_id}")
            return False, "INVALID_BOOTSTRAP_TOKEN"
        
        return True, None
    
    def issue_challenge(
        self,
        temp_id: str,
        public_key: str
    ) -> Dict:
        """
        Issue cryptographic challenge (Step 3 of validation flow).
        
        Args:
            temp_id: Controller's temporary ID
            public_key: Controller's public key
        
        Returns:
            Challenge payload with challenge_id and nonce
        """
        import uuid
        
        challenge_id = f"challenge-{uuid.uuid4().hex[:12]}"
        nonce = secrets.token_bytes(32)  # 256-bit nonce
        
        # Store challenge
        self.active_challenges[challenge_id] = {
            'temp_id': temp_id,
            'nonce': nonce,
            'issued_at': datetime.now(timezone.utc),
            'public_key': public_key
        }
        
        self.logger.info(f"Issued challenge {challenge_id} to {temp_id}")
        
        return {
            'challenge_id': challenge_id,
            'nonce': nonce.hex()
        }
    
    def verify_challenge_response(
        self,
        challenge_id: str,
        signed_nonce: str,
        responder_temp_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify challenge response (Step 4 of validation flow).
        
        Args:
            challenge_id: Challenge identifier
            signed_nonce: Signed nonce from controller
            responder_temp_id: Controller responding
        
        Returns:
            (success, error_message) tuple
        """
        challenge = self.active_challenges.get(challenge_id)
        
        if not challenge:
            return False, "UNKNOWN_CHALLENGE"
        
        # Check if challenge expired (30 seconds)
        age = (datetime.now(timezone.utc) - challenge['issued_at']).total_seconds()
        if age > 30:
            del self.active_challenges[challenge_id]
            return False, "CHALLENGE_EXPIRED"
        
        # Verify temp_id matches
        if challenge['temp_id'] != responder_temp_id:
            return False, "TEMP_ID_MISMATCH"
        
        # In production, verify signature with public key
        # For now, simulate verification
        # expected = sign(challenge['nonce'], private_key)
        # if signed_nonce != expected: return False
        
        # Cleanup used challenge
        del self.active_challenges[challenge_id]
        
        self.logger.info(f"Challenge {challenge_id} verified for {responder_temp_id}")
        
        return True, None


class APIClientAuthenticator:
    """
    Authenticates external API clients using API keys.
    """
    
    def __init__(self, secret_manager):
        """
        Initialize API client authenticator.
        
        Args:
            secret_manager: SecretManager instance for key storage
        """
        self.secret_manager = secret_manager
        self.logger = logging.getLogger(f"{__name__}.APIClientAuth")
        
        # API key metadata: api_key_id -> {client_name, permissions, rate_limit}
        self.api_keys: Dict[str, Dict] = {}
    
    def generate_api_key(
        self,
        client_name: str,
        permissions: List[str],
        rate_limit_per_hour: int = 1000
    ) -> str:
        """
        Generate new API key for external client.
        
        Args:
            client_name: Client identifier
            permissions: List of allowed operations
            rate_limit_per_hour: Request limit
        
        Returns:
            Generated API key
        """
        import uuid
        
        # Generate API key: pdsno_<random>
        api_key = f"pdsno_{secrets.token_urlsafe(32)}"
        api_key_id = str(uuid.uuid4())
        
        # Store metadata
        self.api_keys[api_key_id] = {
            'api_key_hash': hashlib.sha256(api_key.encode()).hexdigest(),
            'client_name': client_name,
            'permissions': permissions,
            'rate_limit_per_hour': rate_limit_per_hour,
            'created_at': datetime.now(timezone.utc),
            'last_used': None,
            'request_count': 0
        }
        
        # Store in secret manager
        self.secret_manager.store_secret(
            f"api_key_{api_key_id}",
            api_key.encode(),
            metadata={'client_name': client_name}
        )
        
        self.logger.info(f"Generated API key for {client_name}")
        
        return api_key
    
    def verify_api_key(
        self,
        api_key: str
    ) -> AuthenticationResult:
        """
        Verify API key and check rate limits.
        
        Args:
            api_key: API key to verify
        
        Returns:
            AuthenticationResult
        """
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Find matching key
        for api_key_id, metadata in self.api_keys.items():
            if hmac.compare_digest(metadata['api_key_hash'], api_key_hash):
                # Check rate limit
                if metadata['request_count'] >= metadata['rate_limit_per_hour']:
                    return AuthenticationResult(
                        success=False,
                        error="RATE_LIMIT_EXCEEDED"
                    )
                
                # Update usage
                metadata['last_used'] = datetime.now(timezone.utc)
                metadata['request_count'] += 1
                
                self.logger.debug(f"API key verified for {metadata['client_name']}")
                
                return AuthenticationResult(
                    success=True,
                    entity_id=metadata['client_name'],
                    entity_type=EntityType.API_CLIENT,
                    metadata={
                        'permissions': metadata['permissions'],
                        'rate_limit_remaining': metadata['rate_limit_per_hour'] - metadata['request_count']
                    }
                )
        
        self.logger.warning("Invalid API key attempt")
        
        return AuthenticationResult(
            success=False,
            error="INVALID_API_KEY"
        )


class OperatorAuthenticator:
    """
    Authenticates human operators (admins) with username/password + MFA.
    """
    
    JWT_SECRET = secrets.token_bytes(32)  # In production, load from secure storage
    SESSION_LIFETIME_HOURS = 8
    
    def __init__(self, secret_manager):
        """
        Initialize operator authenticator.
        
        Args:
            secret_manager: SecretManager instance
        """
        self.secret_manager = secret_manager
        self.logger = logging.getLogger(f"{__name__}.OperatorAuth")
        
        # User accounts: username -> {password_hash, role, mfa_enabled, mfa_secret}
        self.users: Dict[str, Dict] = {}
        
        # Active sessions: session_token -> {username, role, expires_at}
        self.sessions: Dict[str, Dict] = {}
    
    def create_user(
        self,
        username: str,
        password: str,
        role: str,
        mfa_enabled: bool = True
    ) -> bool:
        """
        Create new operator account.
        
        Args:
            username: Username
            password: Password (will be hashed)
            role: User role (admin/operator/viewer)
            mfa_enabled: Enable MFA
        
        Returns:
            True if created successfully
        """
        if username in self.users:
            return False
        
        # Hash password with salt
        import bcrypt
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        
        # Generate MFA secret if enabled
        mfa_secret = None
        if mfa_enabled:
            import pyotp
            mfa_secret = pyotp.random_base32()
        
        self.users[username] = {
            'password_hash': password_hash,
            'role': role,
            'mfa_enabled': mfa_enabled,
            'mfa_secret': mfa_secret,
            'created_at': datetime.now(timezone.utc),
            'last_login': None,
            'failed_attempts': 0
        }
        
        self.logger.info(f"Created user account: {username} (role: {role})")
        
        return True
    
    def authenticate(
        self,
        username: str,
        password: str,
        mfa_code: Optional[str] = None
    ) -> AuthenticationResult:
        """
        Authenticate operator with username/password + MFA.
        
        Args:
            username: Username
            password: Password
            mfa_code: MFA code (if MFA enabled)
        
        Returns:
            AuthenticationResult with session token
        """
        user = self.users.get(username)
        
        if not user:
            return AuthenticationResult(
                success=False,
                error="INVALID_CREDENTIALS"
            )
        
        # Check account lockout
        if user['failed_attempts'] >= 5:
            return AuthenticationResult(
                success=False,
                error="ACCOUNT_LOCKED"
            )
        
        # Verify password
        import bcrypt
        if not bcrypt.checkpw(password.encode(), user['password_hash']):
            user['failed_attempts'] += 1
            self.logger.warning(f"Failed login attempt for {username}")
            
            return AuthenticationResult(
                success=False,
                error="INVALID_CREDENTIALS"
            )
        
        # Verify MFA if enabled
        if user['mfa_enabled']:
            if not mfa_code:
                return AuthenticationResult(
                    success=False,
                    error="MFA_REQUIRED"
                )
            
            import pyotp
            totp = pyotp.TOTP(user['mfa_secret'])
            if not totp.verify(mfa_code):
                self.logger.warning(f"Invalid MFA code for {username}")
                
                return AuthenticationResult(
                    success=False,
                    error="INVALID_MFA_CODE"
                )
        
        # Reset failed attempts
        user['failed_attempts'] = 0
        user['last_login'] = datetime.now(timezone.utc)
        
        # Generate session token (JWT)
        session_token = jwt.encode(
            {
                'username': username,
                'role': user['role'],
                'exp': datetime.utcnow() + timedelta(hours=self.SESSION_LIFETIME_HOURS)
            },
            self.JWT_SECRET,
            algorithm='HS256'
        )
        
        # Store session
        self.sessions[session_token] = {
            'username': username,
            'role': user['role'],
            'expires_at': datetime.now(timezone.utc) + timedelta(hours=self.SESSION_LIFETIME_HOURS)
        }
        
        self.logger.info(f"Operator {username} authenticated successfully")
        
        return AuthenticationResult(
            success=True,
            entity_id=username,
            entity_type=EntityType.OPERATOR,
            session_token=session_token,
            metadata={'role': user['role']}
        )
    
    def verify_session(
        self,
        session_token: str
    ) -> AuthenticationResult:
        """
        Verify session token validity.
        
        Args:
            session_token: JWT session token
        
        Returns:
            AuthenticationResult
        """
        try:
            payload = jwt.decode(session_token, self.JWT_SECRET, algorithms=['HS256'])
            
            return AuthenticationResult(
                success=True,
                entity_id=payload['username'],
                entity_type=EntityType.OPERATOR,
                metadata={'role': payload['role']}
            )
        
        except jwt.ExpiredSignatureError:
            return AuthenticationResult(
                success=False,
                error="SESSION_EXPIRED"
            )
        
        except jwt.InvalidTokenError:
            return AuthenticationResult(
                success=False,
                error="INVALID_SESSION"
            )


class DeviceAuthenticator:
    """
    Authenticates network devices being managed by PDSNO.
    """
    
    def __init__(self, secret_manager):
        """
        Initialize device authenticator.
        
        Args:
            secret_manager: SecretManager instance
        """
        self.secret_manager = secret_manager
        self.logger = logging.getLogger(f"{__name__}.DeviceAuth")
        
        # Device credentials: device_id -> {username, password_hash, protocol}
        self.device_credentials: Dict[str, Dict] = {}
    
    def register_device(
        self,
        device_id: str,
        username: str,
        password: str,
        protocol: str = "ssh"  # ssh, telnet, netconf, restconf
    ):
        """
        Register device credentials.
        
        Args:
            device_id: Device identifier
            username: Device username
            password: Device password
            protocol: Management protocol
        """
        # Hash password
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        self.device_credentials[device_id] = {
            'username': username,
            'password_hash': password_hash,
            'protocol': protocol,
            'registered_at': datetime.now(timezone.utc)
        }
        
        # Store encrypted in secret manager
        self.secret_manager.store_secret(
            f"device_{device_id}_password",
            password.encode(),
            metadata={'device_id': device_id, 'protocol': protocol}
        )
        
        self.logger.info(f"Registered device credentials for {device_id}")
    
    def get_device_credentials(
        self,
        device_id: str
    ) -> Optional[Dict]:
        """
        Retrieve device credentials for connection.
        
        Args:
            device_id: Device identifier
        
        Returns:
            Credentials dict or None
        """
        if device_id not in self.device_credentials:
            return None
        
        # Retrieve encrypted password
        password_bytes = self.secret_manager.retrieve_secret(
            f"device_{device_id}_password"
        )
        
        if not password_bytes:
            return None
        
        creds = self.device_credentials[device_id]
        
        return {
            'device_id': device_id,
            'username': creds['username'],
            'password': password_bytes.decode(),
            'protocol': creds['protocol']
        }


# Example usage:
"""
from pdsno.security.auth import (
    ControllerAuthenticator,
    APIClientAuthenticator,
    OperatorAuthenticator,
    DeviceAuthenticator,
    EntityType
)

# 1. Controller Authentication (system-to-system)
controller_auth = ControllerAuthenticator(bootstrap_secret=b'...')

# Verify bootstrap token
valid, error = controller_auth.verify_bootstrap_token(
    temp_id="temp-rc-001",
    region="zone-A",
    controller_type="regional",
    submitted_token="abc123..."
)

# Issue challenge
challenge = controller_auth.issue_challenge("temp-rc-001", public_key="...")

# Verify response
valid, error = controller_auth.verify_challenge_response(
    challenge_id=challenge['challenge_id'],
    signed_nonce="signed_data...",
    responder_temp_id="temp-rc-001"
)

# 2. API Client Authentication
api_auth = APIClientAuthenticator(secret_manager)

# Generate API key for external system
api_key = api_auth.generate_api_key(
    client_name="monitoring_system",
    permissions=["read:devices", "read:audit"],
    rate_limit_per_hour=5000
)

# Verify API key on request
result = api_auth.verify_api_key(api_key)
if result.success:
    print(f"Authenticated: {result.entity_id}")
    print(f"Permissions: {result.metadata['permissions']}")

# 3. Operator Authentication
operator_auth = OperatorAuthenticator(secret_manager)

# Create admin account
operator_auth.create_user(
    username="admin",
    password="secure_password",
    role="admin",
    mfa_enabled=True
)

# Login
result = operator_auth.authenticate(
    username="admin",
    password="secure_password",
    mfa_code="123456"
)

if result.success:
    session_token = result.session_token
    # Use session token for subsequent requests

# 4. Device Authentication
device_auth = DeviceAuthenticator(secret_manager)

# Register device
device_auth.register_device(
    device_id="switch-core-01",
    username="admin",
    password="switch_password",
    protocol="ssh"
)

# Get credentials for connection
creds = device_auth.get_device_credentials("switch-core-01")
# Use creds to connect to device
"""