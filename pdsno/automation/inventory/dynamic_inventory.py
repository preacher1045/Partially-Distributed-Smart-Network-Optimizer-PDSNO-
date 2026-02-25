#!/usr/bin/env python3
"""
Dynamic Inventory Script for Ansible

Pulls device inventory from PDSNO NIB and formats for Ansible.

Usage:
    python dynamic_inventory.py --list
    python dynamic_inventory.py --host <hostname>
"""

import json
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pdsno.datastore import NIBStore


class DynamicInventory:
    """Generate Ansible inventory from NIB"""
    
    def __init__(self, db_path: str = "config/pdsno.db"):
        """
        Initialize inventory generator.
        
        Args:
            db_path: Path to NIB database
        """
        self.nib = NIBStore(db_path)
    
    def list_all(self) -> dict:
        """
        Generate complete inventory.
        
        Returns:
            Ansible inventory dictionary
        """
        inventory = {
            '_meta': {
                'hostvars': {}
            }
        }
        
        # Get all active devices from NIB
        devices = self.nib.get_all_devices(status='active')
        
        # Group by vendor
        vendors = {}
        regions = {}
        device_types = {}
        
        for device in devices:
            device_id = device.device_id
            
            # Add to hostvars
            inventory['_meta']['hostvars'][device_id] = {
                'ansible_host': device.ip_address,
                'ansible_user': 'admin',  # From secret manager in production
                'device_id': device_id,
                'mac_address': device.mac_address,
                'hostname': device.hostname,
                'vendor': device.vendor,
                'device_type': device.device_type,
                'region': device.region,
                'managed_by': device.managed_by_lc
            }
            
            # Set connection type based on vendor
            if device.vendor == 'cisco':
                inventory['_meta']['hostvars'][device_id]['ansible_connection'] = 'network_cli'
                inventory['_meta']['hostvars'][device_id]['ansible_network_os'] = 'ios'
            
            elif device.vendor == 'juniper':
                inventory['_meta']['hostvars'][device_id]['ansible_connection'] = 'netconf'
                inventory['_meta']['hostvars'][device_id]['ansible_network_os'] = 'junos'
            
            elif device.vendor == 'arista':
                inventory['_meta']['hostvars'][device_id]['ansible_connection'] = 'httpapi'
                inventory['_meta']['hostvars'][device_id]['ansible_network_os'] = 'eos'
            
            # Group by vendor
            if device.vendor not in vendors:
                vendors[device.vendor] = {'hosts': []}
            vendors[device.vendor]['hosts'].append(device_id)
            
            # Group by region
            if device.region not in regions:
                regions[device.region] = {'hosts': []}
            regions[device.region]['hosts'].append(device_id)
            
            # Group by device type
            if device.device_type not in device_types:
                device_types[device.device_type] = {'hosts': []}
            device_types[device.device_type]['hosts'].append(device_id)
        
        # Add groups to inventory
        for vendor, data in vendors.items():
            inventory[vendor] = data
        
        for region, data in regions.items():
            inventory[f"region_{region}"] = data
        
        for dtype, data in device_types.items():
            inventory[dtype] = data
        
        # Add special groups
        inventory['all'] = {
            'children': list(vendors.keys()) + 
                       [f"region_{r}" for r in regions.keys()] +
                       list(device_types.keys())
        }
        
        return inventory
    
    def get_host(self, hostname: str) -> dict:
        """
        Get variables for specific host.
        
        Args:
            hostname: Device ID or hostname
        
        Returns:
            Host variables dictionary
        """
        # Get device from NIB
        device = self.nib.get_device(hostname)
        
        if not device:
            return {}
        
        return {
            'ansible_host': device.ip_address,
            'ansible_user': 'admin',
            'device_id': device.device_id,
            'mac_address': device.mac_address,
            'hostname': device.hostname,
            'vendor': device.vendor,
            'device_type': device.device_type,
            'region': device.region
        }


def main():
    """Main entry point for Ansible"""
    parser = argparse.ArgumentParser(
        description='PDSNO Dynamic Inventory'
    )
    parser.add_argument('--list', action='store_true',
                        help='List all hosts')
    parser.add_argument('--host', help='Get host variables')
    
    args = parser.parse_args()
    
    inventory = DynamicInventory()
    
    if args.list:
        output = inventory.list_all()
    elif args.host:
        output = inventory.get_host(args.host)
    else:
        parser.print_help()
        sys.exit(1)
    
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()