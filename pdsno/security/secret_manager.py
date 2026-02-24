"""
PDSNO Secret Manager

Secure storage and retrieval of sensitive data:
- API keys
- Device credentials (passwords, SSH keys)
- Bootstrap tokens
- Encryption keys
- TLS certificates
- Database passwords

Security Features:
- Encryption at rest (AES-256-GCM)
- Key derivation (PBKDF2)
- Secret rotation tracking
- Access audit logging
- Integration with external KMS (AWS Secrets Manager, HashiCorp Vault)
"""

import os
import json
import secrets
import hashlib
from typing import Dict, Optional, List
from datetime import datetime, timezone, timedelta
from enum import Enum
import logging

# Cryptography imports
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend


class SecretType(Enum):
    """Types of secrets"""
    API_KEY = "api_key"
    DEVICE_PASSWORD = "device_password"
    BOOTSTRAP_TOKEN = "bootstrap_token"
    ENCRYPTION_KEY = "encryption_key"
    TLS_CERTIFICATE = "tls_certificate"
    DATABASE_PASSWORD = "database_password"
    HMAC_KEY = "hmac_key"
    SSH_KEY = "ssh_key"


class SecretMetadata:
    """Metadata for a stored secret"""
    
    def __init__(
        self,
        secret_id: str,
        secret_type: SecretType,
        created_at: datetime,
        expires_at: Optional[datetime] = None,
        last_accessed: Optional[datetime] = None,
        rotation_policy_days: int = 90,
        custom_metadata: Optional[Dict] = None
    ):
        self.secret_id = secret_id
        self.secret_type = secret_type
        self.created_at = created_at
        self.expires_at = expires_at
        self.last_accessed = last_accessed
        self.rotation_policy_days = rotation_policy_days
        self.custom_metadata = custom_metadata or {}
        self.access_count = 0
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            'secret_id': self.secret_id,
            'secret_type': self.secret_type.value,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'rotation_policy_days': self.rotation_policy_days,
            'custom_metadata': self.custom_metadata,
            'access_count': self.access_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SecretMetadata':
        """Deserialize from dictionary"""
        metadata = cls(
            secret_id=data['secret_id'],
            secret_type=SecretType(data['secret_type']),
            created_at=datetime.fromisoformat(data['created_at']),
            expires_at=datetime.fromisoformat(data['expires_at']) if data['expires_at'] else None,
            last_accessed=datetime.fromisoformat(data['last_accessed']) if data['last_accessed'] else None,
            rotation_policy_days=data.get('rotation_policy_days', 90),
            custom_metadata=data.get('custom_metadata', {})
        )
        metadata.access_count = data.get('access_count', 0)
        return metadata


class SecretManager:
    """
    Manages secure storage and retrieval of secrets.
    
    Uses AES-256-GCM for encryption at rest.
    """
    
    def __init__(
        self,
        master_key: Optional[bytes] = None,
        storage_path: str = "./secrets"
    ):
        """
        Initialize secret manager.
        
        Args:
            master_key: Master encryption key (32 bytes). If None, generates new key.
            storage_path: Directory for encrypted secrets
        """
        self.logger = logging.getLogger(__name__)
        
        # Master key for encryption
        if master_key:
            if len(master_key) < 32:
                raise ValueError("Master key must be at least 32 bytes")
            self.master_key = master_key
        else:
            # Generate new master key
            self.master_key = secrets.token_bytes(32)
            self.logger.warning(
                "Generated new master key - store securely! "
                "In production, load from KMS or secure storage."
            )
        
        # Storage
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
        
        # Secret metadata: secret_id -> SecretMetadata
        self.metadata: Dict[str, SecretMetadata] = {}
        
        # Load existing metadata
        self._load_metadata()
    
    def _derive_key(self, salt: bytes) -> bytes:
        """
        Derive encryption key from master key using PBKDF2.
        
        Args:
            salt: Salt for key derivation
        
        Returns:
            Derived key (32 bytes)
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(self.master_key)
    
    def _encrypt(self, plaintext: bytes) -> tuple[bytes, bytes, bytes]:
        """
        Encrypt data with AES-256-GCM.
        
        Args:
            plaintext: Data to encrypt
        
        Returns:
            (ciphertext, salt, nonce) tuple
        """
        # Generate salt and nonce
        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(12)  # GCM nonce
        
        # Derive key
        key = self._derive_key(salt)
        
        # Encrypt
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        
        return ciphertext, salt, nonce
    
    def _decrypt(
        self,
        ciphertext: bytes,
        salt: bytes,
        nonce: bytes
    ) -> bytes:
        """
        Decrypt data with AES-256-GCM.
        
        Args:
            ciphertext: Encrypted data
            salt: Salt used for key derivation
            nonce: Nonce used for encryption
        
        Returns:
            Decrypted plaintext
        """
        # Derive key
        key = self._derive_key(salt)
        
        # Decrypt
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        
        return plaintext
    
    def store_secret(
        self,
        secret_id: str,
        secret_value: bytes,
        secret_type: SecretType = SecretType.API_KEY,
        expires_at: Optional[datetime] = None,
        rotation_policy_days: int = 90,
        metadata: Optional[Dict] = None
    ):
        """
        Store a secret securely.
        
        Args:
            secret_id: Unique identifier for secret
            secret_value: Secret data (bytes)
            secret_type: Type of secret
            expires_at: Optional expiration datetime
            rotation_policy_days: Days until rotation recommended
            metadata: Additional metadata
        """
        # Encrypt secret
        ciphertext, salt, nonce = self._encrypt(secret_value)
        
        # Store encrypted secret
        secret_path = os.path.join(self.storage_path, f"{secret_id}.enc")
        
        with open(secret_path, 'wb') as f:
            # Format: salt (16) + nonce (12) + ciphertext
            f.write(salt + nonce + ciphertext)
        
        # Store metadata
        secret_metadata = SecretMetadata(
            secret_id=secret_id,
            secret_type=secret_type,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            rotation_policy_days=rotation_policy_days,
            custom_metadata=metadata
        )
        
        self.metadata[secret_id] = secret_metadata
        self._save_metadata()
        
        self.logger.info(f"Stored secret: {secret_id} (type: {secret_type.value})")
    
    def retrieve_secret(
        self,
        secret_id: str
    ) -> Optional[bytes]:
        """
        Retrieve and decrypt a secret.
        
        Args:
            secret_id: Secret identifier
        
        Returns:
            Decrypted secret value or None if not found
        """
        metadata = self.metadata.get(secret_id)
        
        if not metadata:
            self.logger.warning(f"Secret not found: {secret_id}")
            return None
        
        # Check expiration
        if metadata.expires_at and datetime.now(timezone.utc) > metadata.expires_at:
            self.logger.warning(f"Secret expired: {secret_id}")
            return None
        
        # Read encrypted secret
        secret_path = os.path.join(self.storage_path, f"{secret_id}.enc")
        
        if not os.path.exists(secret_path):
            self.logger.error(f"Secret file not found: {secret_path}")
            return None
        
        with open(secret_path, 'rb') as f:
            data = f.read()
        
        # Extract salt, nonce, ciphertext
        salt = data[:16]
        nonce = data[16:28]
        ciphertext = data[28:]
        
        # Decrypt
        try:
            plaintext = self._decrypt(ciphertext, salt, nonce)
            
            # Update access metadata
            metadata.last_accessed = datetime.now(timezone.utc)
            metadata.access_count += 1
            self._save_metadata()
            
            self.logger.debug(f"Retrieved secret: {secret_id}")
            
            return plaintext
        
        except Exception as e:
            self.logger.error(f"Failed to decrypt secret {secret_id}: {e}")
            return None
    
    def delete_secret(self, secret_id: str) -> bool:
        """
        Delete a secret.
        
        Args:
            secret_id: Secret to delete
        
        Returns:
            True if deleted
        """
        if secret_id not in self.metadata:
            return False
        
        # Delete file
        secret_path = os.path.join(self.storage_path, f"{secret_id}.enc")
        
        if os.path.exists(secret_path):
            os.remove(secret_path)
        
        # Delete metadata
        del self.metadata[secret_id]
        self._save_metadata()
        
        self.logger.info(f"Deleted secret: {secret_id}")
        
        return True
    
    def rotate_secret(
        self,
        secret_id: str,
        new_secret_value: bytes
    ) -> bool:
        """
        Rotate a secret (delete old, store new).
        
        Args:
            secret_id: Secret to rotate
            new_secret_value: New secret value
        
        Returns:
            True if rotated successfully
        """
        metadata = self.metadata.get(secret_id)
        
        if not metadata:
            return False
        
        # Store new secret (overwrites old)
        self.store_secret(
            secret_id=secret_id,
            secret_value=new_secret_value,
            secret_type=metadata.secret_type,
            expires_at=metadata.expires_at,
            rotation_policy_days=metadata.rotation_policy_days,
            metadata=metadata.custom_metadata
        )
        
        self.logger.info(f"Rotated secret: {secret_id}")
        
        return True
    
    def list_secrets(
        self,
        secret_type: Optional[SecretType] = None
    ) -> List[SecretMetadata]:
        """
        List all secrets (metadata only, not values).
        
        Args:
            secret_type: Optional filter by type
        
        Returns:
            List of secret metadata
        """
        secrets_list = list(self.metadata.values())
        
        if secret_type:
            secrets_list = [s for s in secrets_list if s.secret_type == secret_type]
        
        return secrets_list
    
    def check_rotation_needed(self) -> List[str]:
        """
        Check which secrets need rotation based on policy.
        
        Returns:
            List of secret IDs needing rotation
        """
        now = datetime.now(timezone.utc)
        needs_rotation = []
        
        for secret_id, metadata in self.metadata.items():
            age_days = (now - metadata.created_at).days
            
            if age_days >= metadata.rotation_policy_days:
                needs_rotation.append(secret_id)
        
        return needs_rotation
    
    def _load_metadata(self):
        """Load secret metadata from disk"""
        metadata_path = os.path.join(self.storage_path, "metadata.json")
        
        if not os.path.exists(metadata_path):
            return
        
        try:
            with open(metadata_path, 'r') as f:
                data = json.load(f)
            
            for secret_id, meta_dict in data.items():
                self.metadata[secret_id] = SecretMetadata.from_dict(meta_dict)
            
            self.logger.info(f"Loaded metadata for {len(self.metadata)} secrets")
        
        except Exception as e:
            self.logger.error(f"Failed to load metadata: {e}")
    
    def _save_metadata(self):
        """Save secret metadata to disk"""
        metadata_path = os.path.join(self.storage_path, "metadata.json")
        
        data = {
            secret_id: metadata.to_dict()
            for secret_id, metadata in self.metadata.items()
        }
        
        with open(metadata_path, 'w') as f:
            json.dump(data, f, indent=2)


class ExternalKMSAdapter:
    """
    Adapter for external Key Management Services.
    
    Supports:
    - AWS Secrets Manager
    - HashiCorp Vault
    - Azure Key Vault
    """
    
    def __init__(self, kms_type: str, config: Dict):
        """
        Initialize KMS adapter.
        
        Args:
            kms_type: "aws", "vault", or "azure"
            config: KMS-specific configuration
        """
        self.kms_type = kms_type
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.KMS")
    
    def store_secret(self, secret_id: str, secret_value: str) -> bool:
        """Store secret in external KMS"""
        if self.kms_type == "aws":
            return self._store_aws(secret_id, secret_value)
        elif self.kms_type == "vault":
            return self._store_vault(secret_id, secret_value)
        elif self.kms_type == "azure":
            return self._store_azure(secret_id, secret_value)
        else:
            raise ValueError(f"Unsupported KMS type: {self.kms_type}")
    
    def retrieve_secret(self, secret_id: str) -> Optional[str]:
        """Retrieve secret from external KMS"""
        if self.kms_type == "aws":
            return self._retrieve_aws(secret_id)
        elif self.kms_type == "vault":
            return self._retrieve_vault(secret_id)
        elif self.kms_type == "azure":
            return self._retrieve_azure(secret_id)
        else:
            raise ValueError(f"Unsupported KMS type: {self.kms_type}")
    
    def _store_aws(self, secret_id: str, secret_value: str) -> bool:
        """Store in AWS Secrets Manager"""
        try:
            import boto3
            
            client = boto3.client('secretsmanager', region_name=self.config['region'])
            
            client.create_secret(
                Name=secret_id,
                SecretString=secret_value
            )
            
            self.logger.info(f"Stored secret in AWS: {secret_id}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to store in AWS: {e}")
            return False
    
    def _retrieve_aws(self, secret_id: str) -> Optional[str]:
        """Retrieve from AWS Secrets Manager"""
        try:
            import boto3
            
            client = boto3.client('secretsmanager', region_name=self.config['region'])
            
            response = client.get_secret_value(SecretId=secret_id)
            
            return response['SecretString']
        
        except Exception as e:
            self.logger.error(f"Failed to retrieve from AWS: {e}")
            return None
    
    def _store_vault(self, secret_id: str, secret_value: str) -> bool:
        """Store in HashiCorp Vault"""
        try:
            import hvac
            
            client = hvac.Client(
                url=self.config['url'],
                token=self.config['token']
            )
            
            client.secrets.kv.v2.create_or_update_secret(
                path=secret_id,
                secret={'value': secret_value}
            )
            
            self.logger.info(f"Stored secret in Vault: {secret_id}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to store in Vault: {e}")
            return False
    
    def _retrieve_vault(self, secret_id: str) -> Optional[str]:
        """Retrieve from HashiCorp Vault"""
        try:
            import hvac
            
            client = hvac.Client(
                url=self.config['url'],
                token=self.config['token']
            )
            
            response = client.secrets.kv.v2.read_secret_version(path=secret_id)
            
            return response['data']['data']['value']
        
        except Exception as e:
            self.logger.error(f"Failed to retrieve from Vault: {e}")
            return None
    
    def _store_azure(self, secret_id: str, secret_value: str) -> bool:
        """Store in Azure Key Vault"""
        # Implementation would use azure-keyvault-secrets
        raise NotImplementedError("Azure Key Vault not yet implemented")
    
    def _retrieve_azure(self, secret_id: str) -> Optional[str]:
        """Retrieve from Azure Key Vault"""
        raise NotImplementedError("Azure Key Vault not yet implemented")


# Example usage:
"""
from pdsno.security.secret_manager import SecretManager, SecretType

# Initialize secret manager
secret_mgr = SecretManager(master_key=b'...')  # In production, load from secure storage

# Store secrets

# 1. API Key
api_key = "pdsno_abc123xyz789"
secret_mgr.store_secret(
    secret_id="monitoring_api_key",
    secret_value=api_key.encode(),
    secret_type=SecretType.API_KEY,
    metadata={'client': 'monitoring_system'}
)

# 2. Device password
secret_mgr.store_secret(
    secret_id="device_switch-core-01_password",
    secret_value=b"switch_password",
    secret_type=SecretType.DEVICE_PASSWORD,
    metadata={'device_id': 'switch-core-01', 'protocol': 'ssh'}
)

# 3. Bootstrap token
secret_mgr.store_secret(
    secret_id="bootstrap_token_zone-A",
    secret_value=b"bootstrap_secret_abc123",
    secret_type=SecretType.BOOTSTRAP_TOKEN,
    rotation_policy_days=30
)

# Retrieve secrets
api_key_bytes = secret_mgr.retrieve_secret("monitoring_api_key")
if api_key_bytes:
    api_key = api_key_bytes.decode()
    print(f"Retrieved API key: {api_key[:10]}...")

# Check rotation needed
needs_rotation = secret_mgr.check_rotation_needed()
for secret_id in needs_rotation:
    print(f"Secret needs rotation: {secret_id}")

# Rotate secret
new_token = secrets.token_bytes(32)
secret_mgr.rotate_secret("bootstrap_token_zone-A", new_token)

# List all secrets
all_secrets = secret_mgr.list_secrets()
for metadata in all_secrets:
    print(f"{metadata.secret_id}: {metadata.secret_type.value}")

# Delete secret
secret_mgr.delete_secret("old_api_key")
"""