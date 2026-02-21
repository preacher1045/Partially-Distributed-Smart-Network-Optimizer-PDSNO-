"""
SNMP Scanner Algorithm

Enriches device data by querying SNMP (vendor, hostname, interfaces).
Optional - gracefully fails if SNMP not available.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pdsno.core.base_class import AlgorithmBase
from pdsno.logging.logger import get_logger


class SNMPScanner(AlgorithmBase):
    """
    SNMP-based device enrichment.
    
    Queries devices for additional information beyond what ARP/ICMP provide.
    """
    
    # Standard SNMP OIDs
    OID_SYSNAME = "1.3.6.1.2.1.1.5.0"      # System name (hostname)
    OID_SYSDESCR = "1.3.6.1.2.1.1.1.0"     # System description (vendor/model)
    OID_SYSUPTIME = "1.3.6.1.2.1.1.3.0"    # System uptime
    
    def __init__(self):
        super().__init__()
        self.ip_list: List[str] = []
        self.community: str = "public"
        self.enriched_devices: List[Dict] = []
        self.logger = get_logger(self.__class__.__name__)
    
    def initialize(self, context: Dict):
        """
        Initialize scanner with list of IPs to query.
        
        Args:
            context: Must contain 'ip_list'. Optional: 'community' (default: 'public')
        """
        self.ip_list = context.get('ip_list', [])
        self.community = context.get('community', 'public')
        
        if not self.ip_list:
            raise ValueError("Context must contain non-empty 'ip_list'")
        
        self.logger.info(f"SNMP Scanner initialized with {len(self.ip_list)} targets")
        self._initialized = True
    
    def execute(self) -> List[Dict]:
        """
        Execute SNMP queries on all target IPs.
        
        Returns:
            List of enriched devices: [{"ip": "...", "hostname": "...", "vendor": "...", ...}, ...]
        """
        super().execute()  # Validate lifecycle
        
        self.logger.info(f"Starting SNMP query of {len(self.ip_list)} addresses")
        start_time = datetime.now(timezone.utc)
        
        try:
            # Run async SNMP queries
            self.enriched_devices = asyncio.run(self._query_all())
            
            scan_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.logger.info(
                f"SNMP scan complete: {len(self.enriched_devices)}/{len(self.ip_list)} "
                f"responded in {scan_duration:.2f}s"
            )
            
            self._executed = True
            return self.enriched_devices
            
        except Exception as e:
            self.logger.error(f"SNMP scan failed: {e}", exc_info=True)
            # Don't raise - SNMP failure is non-critical
            return []
    
    def finalize(self) -> Dict:
        """Return scan results with metadata"""
        super().finalize()  # Validate lifecycle
        
        return {
            "status": "complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "targets_queried": len(self.ip_list),
            "devices_responded": len(self.enriched_devices),
            "devices": self.enriched_devices
        }
    
    async def _query_all(self) -> List[Dict]:
        """Query all IPs concurrently"""
        tasks = [self._query_single(ip) for ip in self.ip_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None and exceptions
        enriched = []
        for result in results:
            if result and not isinstance(result, Exception):
                enriched.append(result)
        
        return enriched
    
    async def _query_single(self, ip: str) -> Optional[Dict]:
        """
        Query a single device via SNMP.
        
        Returns:
            Device info dict if SNMP succeeds, None otherwise
        """
        try:
            # PoC: Simulate SNMP response
            # Real implementation would use pysnmp or easysnmp
            await asyncio.sleep(0.01)  # Simulate query latency
            
            # Simulate 50% success rate
            import random
            if random.random() < 0.5:
                return {
                    "ip": ip,
                    "hostname": f"device-{ip.split('.')[-1]}",
                    "vendor": random.choice(["Cisco", "Juniper", "Arista", "HP"]),
                    "model": random.choice(["Switch", "Router", "Firewall"]),
                    "uptime_seconds": random.randint(3600, 86400 * 30),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "protocol": "SNMP"
                }
            
            return None
            
        except Exception as e:
            self.logger.debug(f"SNMP query to {ip} failed: {e}")
            return None


# Real pysnmp-based implementation (for reference, not used in PoC):
"""
async def _query_single_real(self, ip: str, timeout: int = 2) -> Optional[Dict]:
    '''Query device using real SNMP'''
    try:
        from pysnmp.hlapi.asyncio import *
        
        # Query sysName
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(self.community),
            UdpTransportTarget((ip, 161), timeout=timeout),
            ContextData(),
            ObjectType(ObjectIdentity(self.OID_SYSNAME)),
            ObjectType(ObjectIdentity(self.OID_SYSDESCR)),
            ObjectType(ObjectIdentity(self.OID_SYSUPTIME))
        )
        
        errorIndication, errorStatus, errorIndex, varBinds = await iterator
        
        if errorIndication or errorStatus:
            return None
        
        # Parse results
        hostname = None
        description = None
        uptime = None
        
        for varBind in varBinds:
            oid, val = varBind
            oid_str = str(oid)
            
            if oid_str.endswith(self.OID_SYSNAME):
                hostname = str(val)
            elif oid_str.endswith(self.OID_SYSDESCR):
                description = str(val)
            elif oid_str.endswith(self.OID_SYSUPTIME):
                uptime = int(val)
        
        # Parse vendor from description (heuristic)
        vendor = None
        if description:
            for v in ["Cisco", "Juniper", "Arista", "HP", "Dell"]:
                if v.lower() in description.lower():
                    vendor = v
                    break
        
        return {
            "ip": ip,
            "hostname": hostname,
            "vendor": vendor,
            "description": description,
            "uptime_seconds": uptime,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "protocol": "SNMP"
        }
        
    except Exception as e:
        self.logger.debug(f"SNMP query to {ip} failed: {e}")
        return None
"""