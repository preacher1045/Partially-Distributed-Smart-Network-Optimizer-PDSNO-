"""
Rate Limiter for PDSNO

Implements token bucket algorithm for rate limiting:
- API endpoints (requests per minute)
- Authentication attempts (prevent brute force)
- Message processing (prevent flooding)
- DDoS protection
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
import logging
import time


class TokenBucket:
    """
    Token bucket rate limiter implementation.
    
    Tokens are added at a constant rate.
    Each request consumes one token.
    If no tokens available, request is denied.
    """
    
    def __init__(
        self,
        rate: float,  # Tokens per second
        capacity: int  # Bucket capacity
    ):
        """
        Initialize token bucket.
        
        Args:
            rate: Token refill rate (tokens/second)
            capacity: Maximum tokens in bucket
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.time()
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Attempt to consume tokens.
        
        Args:
            tokens: Number of tokens to consume
        
        Returns:
            True if tokens consumed, False if insufficient
        """
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        else:
            return False
    
    def _refill(self):
        """Refill tokens based on time elapsed"""
        now = time.time()
        time_passed = now - self.last_refill
        
        # Calculate tokens to add
        tokens_to_add = time_passed * self.rate
        
        # Add tokens up to capacity
        self.tokens = min(
            self.capacity,
            self.tokens + tokens_to_add
        )
        
        self.last_refill = now
    
    def get_tokens(self) -> float:
        """Get current token count"""
        self._refill()
        return self.tokens


class RateLimiter:
    """
    Multi-client rate limiter.
    
    Tracks separate token buckets for each client.
    """
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 10
    ):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Sustained rate limit
            burst_size: Maximum burst size
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.rate = requests_per_minute / 60.0  # Convert to per-second
        self.logger = logging.getLogger(__name__)
        
        # Client buckets: client_id -> TokenBucket
        self.buckets: Dict[str, TokenBucket] = {}
        
        # Track violations for alerting
        self.violations: Dict[str, int] = {}
    
    def allow_request(
        self,
        client_id: str,
        cost: int = 1
    ) -> tuple[bool, Optional[str]]:
        """
        Check if request should be allowed.
        
        Args:
            client_id: Client identifier (IP, API key, controller ID)
            cost: Token cost of request (default 1)
        
        Returns:
            (allowed, reason) tuple
        """
        # Get or create bucket for client
        if client_id not in self.buckets:
            self.buckets[client_id] = TokenBucket(
                rate=self.rate,
                capacity=self.burst_size
            )
        
        bucket = self.buckets[client_id]
        
        # Try to consume tokens
        if bucket.consume(cost):
            # Reset violation count on success
            if client_id in self.violations:
                del self.violations[client_id]
            return True, None
        else:
            # Track violation
            self.violations[client_id] = self.violations.get(client_id, 0) + 1
            
            self.logger.warning(
                f"Rate limit exceeded for {client_id} "
                f"(violations: {self.violations[client_id]})"
            )
            
            # Calculate retry-after time
            retry_after = int((cost - bucket.get_tokens()) / self.rate)
            
            return False, f"Rate limit exceeded. Retry after {retry_after} seconds"
    
    def get_remaining(self, client_id: str) -> int:
        """Get remaining tokens for client"""
        if client_id not in self.buckets:
            return self.burst_size
        
        return int(self.buckets[client_id].get_tokens())
    
    def get_violations(self, client_id: str) -> int:
        """Get violation count for client"""
        return self.violations.get(client_id, 0)
    
    def reset_client(self, client_id: str):
        """Reset rate limit for specific client"""
        if client_id in self.buckets:
            del self.buckets[client_id]
        if client_id in self.violations:
            del self.violations[client_id]
        
        self.logger.info(f"Reset rate limit for {client_id}")
    
    def cleanup_old_buckets(self, max_idle_seconds: int = 3600):
        """Remove buckets for clients that haven't made requests recently"""
        current_time = time.time()
        to_remove = []
        
        for client_id, bucket in self.buckets.items():
            idle_time = current_time - bucket.last_refill
            if idle_time > max_idle_seconds:
                to_remove.append(client_id)
        
        for client_id in to_remove:
            del self.buckets[client_id]
            if client_id in self.violations:
                del self.violations[client_id]
        
        if to_remove:
            self.logger.debug(f"Cleaned up {len(to_remove)} idle buckets")


class AuthenticationRateLimiter(RateLimiter):
    """
    Specialized rate limiter for authentication attempts.
    
    More restrictive to prevent brute force attacks.
    """
    
    def __init__(
        self,
        attempts_per_minute: int = 5,
        lockout_threshold: int = 10,
        lockout_duration_minutes: int = 15
    ):
        """
        Initialize authentication rate limiter.
        
        Args:
            attempts_per_minute: Login attempts allowed per minute
            lockout_threshold: Failed attempts before lockout
            lockout_duration_minutes: Lockout duration
        """
        super().__init__(
            requests_per_minute=attempts_per_minute,
            burst_size=attempts_per_minute
        )
        
        self.lockout_threshold = lockout_threshold
        self.lockout_duration = timedelta(minutes=lockout_duration_minutes)
        
        # Track lockouts: client_id -> lockout_until
        self.lockouts: Dict[str, datetime] = {}
    
    def allow_authentication_attempt(
        self,
        client_id: str
    ) -> tuple[bool, Optional[str]]:
        """
        Check if authentication attempt should be allowed.
        
        Args:
            client_id: Client identifier (username, IP)
        
        Returns:
            (allowed, reason) tuple
        """
        # Check if currently locked out
        if client_id in self.lockouts:
            lockout_until = self.lockouts[client_id]
            
            if datetime.now() < lockout_until:
                remaining = (lockout_until - datetime.now()).total_seconds()
                return False, f"Account locked. Try again in {int(remaining)} seconds"
            else:
                # Lockout expired
                del self.lockouts[client_id]
                self.reset_client(client_id)
        
        # Check rate limit
        allowed, reason = self.allow_request(client_id)
        
        # If too many violations, initiate lockout
        if not allowed:
            violations = self.get_violations(client_id)
            
            if violations >= self.lockout_threshold:
                lockout_until = datetime.now() + self.lockout_duration
                self.lockouts[client_id] = lockout_until
                
                self.logger.warning(
                    f"Account {client_id} locked out until {lockout_until} "
                    f"(violations: {violations})"
                )
                
                return False, f"Account locked due to too many failed attempts"
        
        return allowed, reason


# Example usage:
"""
from pdsno.security.rate_limiter import RateLimiter, AuthenticationRateLimiter

# API rate limiting
api_limiter = RateLimiter(
    requests_per_minute=100,
    burst_size=20
)

# Check if request allowed
allowed, reason = api_limiter.allow_request(client_id="192.168.1.100")
if not allowed:
    return {"error": reason}, 429

# Authentication rate limiting
auth_limiter = AuthenticationRateLimiter(
    attempts_per_minute=5,
    lockout_threshold=10,
    lockout_duration_minutes=15
)

# Check if login attempt allowed
allowed, reason = auth_limiter.allow_authentication_attempt(username="alice")
if not allowed:
    return {"error": reason}, 429

# Get remaining requests
remaining = api_limiter.get_remaining("192.168.1.100")
print(f"Remaining requests: {remaining}")

# Reset client (admin action)
api_limiter.reset_client("192.168.1.100")
"""