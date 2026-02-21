"""
ARP Scanner Algorithm

Discovers active devices on a subnet by sending ARP requests and collecting responses.
Returns a list of {ip, mac} pairs.
"""

import asyncio
import ipaddress
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pdsno.core.base_class import AlgorithmBase
from pdsno.logging.logger import get_logger


class ARPScanner(AlgorithmBase):
    """
    ARP-based device discovery algorithm.
    
    Sends ARP requests to all IPs in the given subnet and collects responses.
    Works only on local L2 networks (same broadcast domain).
    """
    
    def __init__(self):
        super().__init__()
        self.subnet: Optional[ipaddress.IPv4Network] = None
        self.discovered_devices: List[Dict] = []
        self.logger = get_logger(self.__class__.__name__)
    
    def initialize(self, context: Dict):
        """
        Initialize scanner with subnet to scan.
        
        Args:
            context: Must contain 'subnet' key (e.g., '192.168.1.0/24')
        """
        subnet_str = context.get('subnet')
        if not subnet_str:
            raise ValueError("Context must contain 'subnet' key")
        
        try:
            self.subnet = ipaddress.IPv4Network(subnet_str, strict=False)
        except ValueError as e:
            raise ValueError(f"Invalid subnet format: {e}")
        
        self.logger.info(f"ARP Scanner initialized for subnet {self.subnet}")
        self._initialized = True
    
    def execute(self) -> List[Dict]:
        """
        Execute ARP scan on the configured subnet.
        
        Returns:
            List of discovered devices: [{"ip": "...", "mac": "...", "timestamp": "..."}, ...]
        """
        super().execute()  # Validate lifecycle
        
        self.logger.info(f"Starting ARP scan of {self.subnet} ({self.subnet.num_addresses} addresses)")
        start_time = datetime.now(timezone.utc)
        
        try:
            # Run async ARP scan
            self.discovered_devices = asyncio.run(self._scan_subnet())
            
            scan_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.logger.info(
                f"ARP scan complete: {len(self.discovered_devices)} devices found in {scan_duration:.2f}s"
            )
            
            self._executed = True
            return self.discovered_devices
            
        except Exception as e:
            self.logger.error(f"ARP scan failed: {e}", exc_info=True)
            raise
    
    def finalize(self) -> Dict:
        """Return scan results with metadata"""
        super().finalize()  # Validate lifecycle
        
        return {
            "status": "complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "subnet": str(self.subnet),
            "devices_found": len(self.discovered_devices),
            "devices": self.discovered_devices
        }
    
    async def _scan_subnet(self) -> List[Dict]:
        """
        Async ARP scan implementation.
        
        Sends ARP requests concurrently to all IPs in subnet.
        """
        # For PoC, we'll use a simulated scan
        # Real implementation would use scapy: Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=ip)
        
        # Create tasks for each IP in subnet
        tasks = []
        for ip in self.subnet.hosts():  # .hosts() excludes network and broadcast
            tasks.append(self._arp_request(str(ip)))
        
        # Run all ARP requests concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None and exceptions
        devices = []
        for result in results:
            if result and not isinstance(result, Exception):
                devices.append(result)
        
        return devices
    
    async def _arp_request(self, ip: str) -> Optional[Dict]:
        """
        Send ARP request to a single IP.
        
        Returns:
            {"ip": "...", "mac": "...", "timestamp": "..."} if host responds, None otherwise
        """
        try:
            # Simulate ARP request with small delay
            await asyncio.sleep(0.001)  # Simulate network latency
            
            # PoC: Simulate some hosts responding
            # Real implementation: send ARP packet and wait for response
            # from scapy.all import ARP, Ether, srp
            # answered, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=ip), timeout=timeout, verbose=0)
            
            # Simulate 20% response rate for testing
            import random
            if random.random() < 0.2:
                # Simulate MAC address
                mac = self._generate_fake_mac(ip)
                return {
                    "ip": ip,
                    "mac": mac,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "protocol": "ARP"
                }
            
            return None
            
        except Exception as e:
            self.logger.debug(f"ARP request to {ip} failed: {e}")
            return None
    
    @staticmethod
    def _generate_fake_mac(ip: str) -> str:
        """Generate a fake but consistent MAC address for testing"""
        # Hash the IP to get consistent MAC for same IP across runs
        import hashlib
        hash_bytes = hashlib.md5(ip.encode()).digest()[:6]
        return ":".join(f"{b:02x}" for b in hash_bytes)


# Real scapy-based implementation (for reference, not used in PoC):
"""
async def _arp_request_real(self, ip: str, timeout: float = 1.0) -> Optional[Dict]:
    '''Send real ARP request using scapy'''
    try:
        from scapy.all import ARP, Ether, srp
        
        # Create ARP request packet
        arp = ARP(pdst=ip)
        ether = Ether(dst="ff:ff:ff:ff:ff:ff")
        packet = ether / arp
        
        # Send and wait for response
        answered, _ = srp(packet, timeout=timeout, verbose=False)
        
        if answered:
            for sent, received in answered:
                return {
                    "ip": received.psrc,
                    "mac": received.hwsrc,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "protocol": "ARP"
                }
        
        return None
        
    except Exception as e:
        self.logger.debug(f"ARP request to {ip} failed: {e}")
        return None
"""