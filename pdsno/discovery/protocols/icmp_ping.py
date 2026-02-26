"""
ICMP Ping Scanner Algorithm

Verifies device reachability using ICMP echo requests (ping).
Measures round-trip time (RTT).
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pdsno.core.base_class import AlgorithmBase
from pdsno.logging.logger import get_logger


class ICMPScanner(AlgorithmBase):
    """
    ICMP ping-based reachability verification.
    
    Takes a list of IP addresses and pings each one to verify reachability.
    """
    
    def __init__(self):
        super().__init__()
        self.ip_list: List[str] = []
        self.reachable_devices: List[Dict] = []
        self.logger = get_logger(self.__class__.__name__)
    
    def initialize(self, context: Dict):
        """
        Initialize scanner with list of IPs to ping.
        
        Args:
            context: Must contain 'ip_list' key with list of IP addresses
        """
        self.ip_list = context.get('ip_list', [])
        if not self.ip_list:
            raise ValueError("Context must contain non-empty 'ip_list'")
        
        self.logger.info(f"ICMP Scanner initialized with {len(self.ip_list)} targets")
        self._initialized = True
    
    def execute(self) -> List[Dict]:
        """
        Execute ICMP ping on all target IPs.
        
        Returns:
            List of reachable devices: [{"ip": "...", "rtt_ms": ..., "timestamp": "..."}, ...]
        """
        super().execute()  # Validate lifecycle
        
        self.logger.info(f"Starting ICMP ping of {len(self.ip_list)} addresses")
        start_time = datetime.now(timezone.utc)
        
        try:
            # Run async ping
            self.reachable_devices = asyncio.run(self._ping_all())
            
            scan_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.logger.info(
                f"ICMP scan complete: {len(self.reachable_devices)}/{len(self.ip_list)} " 
                f"reachable in {scan_duration:.2f}s"
            )
            
            self._executed = True
            return self.reachable_devices
            
        except Exception as e:
            self.logger.error(f"ICMP scan failed: {e}", exc_info=True)
            raise
    
    def finalize(self) -> Dict:
        """Return scan results with metadata"""
        super().finalize()  # Validate lifecycle
        
        return {
            "status": "complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "targets_scanned": len(self.ip_list),
            "devices_reachable": len(self.reachable_devices),
            "devices": self.reachable_devices
        }
    
    async def _ping_all(self) -> List[Dict]:
        """Ping all IPs concurrently"""
        tasks = [self._ping_single(ip) for ip in self.ip_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None and exceptions
        reachable = []
        for result in results:
            if result and not isinstance(result, Exception):
                reachable.append(result)
        
        return reachable
    
    async def _ping_single(self, ip: str, count: int = 1, timeout: int = 1) -> Optional[Dict]:
        """
        Ping a single IP address.
        
        Returns:
            {"ip": "...", "rtt_ms": ..., "timestamp": "..."} if reachable, None otherwise
        """
        try:
            # Use subprocess to call system ping command
            # Platform-specific: -c for Linux/Mac, -n for Windows
            import platform
            if platform.system().lower() == "windows":
                cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), ip]
            else:
                cmd = ["ping", "-c", str(count), "-W", str(timeout), ip]
            
            # Run ping
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await proc.communicate()
            
            if proc.returncode == 0:
                # Parse RTT from output (simplified)
                rtt_ms = self._parse_rtt(stdout.decode())
                
                return {
                    "ip": ip,
                    "rtt_ms": rtt_ms,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "protocol": "ICMP"
                }
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Ping to {ip} failed: {e}")
            return None
    
    @staticmethod
    def _parse_rtt(ping_output: str) -> float:
        """
        Parse RTT from ping output.
        
        Very simplified - just looks for "time=" pattern.
        Real implementation would be more robust.
        """
        import re
        
        # Look for pattern like "time=0.123 ms"
        match = re.search(r'time[=<](\d+\.?\d*)\s*ms', ping_output)
        if match:
            return float(match.group(1))
        
        # Default to 1.0ms if parsing fails
        return 1.0