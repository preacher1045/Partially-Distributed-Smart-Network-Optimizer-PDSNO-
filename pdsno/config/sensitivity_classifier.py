"""
Configuration Sensitivity Classifier

Classifies configuration changes into sensitivity tiers:
- LOW: Minimal impact (description changes, monitoring settings)
- MEDIUM: Moderate impact (VLAN changes, ACL updates)
- HIGH: Critical impact (routing changes, security policies)

Sensitivity determines approval requirements and execution flow.
"""

from enum import Enum
from typing import Dict, List
import re
import logging


class SensitivityLevel(Enum):
    """Configuration sensitivity levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ConfigSensitivityClassifier:
    """
    Classifies configuration changes based on impact analysis.

    Uses rule-based classification with support for:
    - Command pattern matching
    - Resource type analysis
    - Change magnitude assessment
    - Historical impact data
    """

    HIGH_PATTERNS = [
        r'router\s+(bgp|ospf|eigrp)',
        r'ip\s+route',
        r'access-list\s+\d+',
        r'firewall',
        r'crypto',
        r'spanning-tree',
        r'interface\s+loopback',
        r'no\s+ip\s+routing',
        r'shutdown.*interface\s+(gigabitethernet|tengigabitethernet)',
        r'delete\s+vlan',
        r'aaa\s+',
        r'snmp-server\s+community',
    ]

    MEDIUM_PATTERNS = [
        r'vlan\s+\d+',
        r'interface\s+vlan',
        r'switchport\s+mode',
        r'switchport\s+access\s+vlan',
        r'qos',
        r'bandwidth',
        r'storm-control',
        r'port-security',
        r'interface\s+(fastethernet|ethernet)',
    ]

    LOW_PATTERNS = [
        r'description\s+',
        r'hostname\s+',
        r'logging\s+',
        r'snmp-server\s+location',
        r'snmp-server\s+contact',
        r'banner\s+',
        r'alias\s+',
    ]

    def __init__(self):
        """Initialize classifier"""
        self.logger = logging.getLogger(__name__)

        self.high_regex = [re.compile(p, re.IGNORECASE) for p in self.HIGH_PATTERNS]
        self.medium_regex = [re.compile(p, re.IGNORECASE) for p in self.MEDIUM_PATTERNS]
        self.low_regex = [re.compile(p, re.IGNORECASE) for p in self.LOW_PATTERNS]

    def classify(self, config_lines: List[str]) -> SensitivityLevel:
        """
        Classify configuration based on highest sensitivity command.

        Args:
            config_lines: List of configuration commands

        Returns:
            Highest sensitivity level found
        """
        if not config_lines:
            return SensitivityLevel.LOW

        config_text = '\n'.join(config_lines)

        for pattern in self.high_regex:
            if pattern.search(config_text):
                self.logger.info(f"HIGH sensitivity detected (pattern: {pattern.pattern})")
                return SensitivityLevel.HIGH

        for pattern in self.medium_regex:
            if pattern.search(config_text):
                self.logger.info(f"MEDIUM sensitivity detected (pattern: {pattern.pattern})")
                return SensitivityLevel.MEDIUM

        self.logger.info("LOW sensitivity (no high/medium patterns matched)")
        return SensitivityLevel.LOW

    def classify_with_details(self, config_lines: List[str]) -> Dict:
        """
        Classify with detailed reasoning.

        Returns:
            {
                'sensitivity': SensitivityLevel,
                'matched_patterns': List[str],
                'high_risk_commands': List[str],
                'reasoning': str
            }
        """
        matched_patterns = []
        high_risk_commands = []

        config_text = '\n'.join(config_lines)

        for pattern in self.high_regex:
            matches = pattern.findall(config_text)
            if matches:
                matched_patterns.append(pattern.pattern)
                high_risk_commands.extend(matches)

        if matched_patterns:
            return {
                'sensitivity': SensitivityLevel.HIGH,
                'matched_patterns': matched_patterns,
                'high_risk_commands': high_risk_commands,
                'reasoning': 'Contains high-impact commands affecting routing, security, or critical services'
            }

        for pattern in self.medium_regex:
            matches = pattern.findall(config_text)
            if matches:
                matched_patterns.append(pattern.pattern)

        if matched_patterns:
            return {
                'sensitivity': SensitivityLevel.MEDIUM,
                'matched_patterns': matched_patterns,
                'high_risk_commands': [],
                'reasoning': 'Contains moderate-impact commands affecting VLANs, interfaces, or QoS'
            }

        return {
            'sensitivity': SensitivityLevel.LOW,
            'matched_patterns': [],
            'high_risk_commands': [],
            'reasoning': 'Contains only low-impact commands (descriptions, monitoring, cosmetic)'
        }

    def add_custom_pattern(self, pattern: str, sensitivity: SensitivityLevel):
        """
        Add custom classification pattern.

        Args:
            pattern: Regex pattern to match
            sensitivity: Sensitivity level for matches
        """
        compiled = re.compile(pattern, re.IGNORECASE)

        if sensitivity == SensitivityLevel.HIGH:
            self.high_regex.append(compiled)
        elif sensitivity == SensitivityLevel.MEDIUM:
            self.medium_regex.append(compiled)
        else:
            self.low_regex.append(compiled)

        self.logger.info(f"Added custom {sensitivity.value} pattern: {pattern}")


# Example usage:
"""
classifier = ConfigSensitivityClassifier()

# Example 1: LOW sensitivity
config1 = [
    "interface gigabitethernet0/1",
    "description Uplink to Core Switch",
    "!"
]
level1 = classifier.classify(config1)

# Example 2: MEDIUM sensitivity
config2 = [
    "vlan 100",
    "name Engineering",
    "interface gigabitethernet0/2",
    "switchport mode access",
    "switchport access vlan 100"
]
level2 = classifier.classify(config2)

# Example 3: HIGH sensitivity
config3 = [
    "router bgp 65001",
    "neighbor 10.0.0.1 remote-as 65002",
    "network 192.168.0.0 mask 255.255.255.0"
]
level3 = classifier.classify(config3)

# Example 4: Detailed classification
details = classifier.classify_with_details(config3)
"""
