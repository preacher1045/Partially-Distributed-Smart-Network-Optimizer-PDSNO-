#!/usr/bin/env python3
"""
PDSNO Load Testing Script

Simulates realistic load on the system to verify performance.

Usage:
    python scripts/load_test.py --scenario validation
    python scripts/load_test.py --scenario discovery --devices 1000
    python scripts/load_test.py --scenario config_approval --rate 100
"""

import argparse
import time
import threading
import queue
from datetime import datetime, timezone
from typing import List, Dict
import statistics


class LoadTestScenario:
    """Base class for load test scenarios"""
    
    def __init__(self, name: str):
        self.name = name
        self.results = []
        self.errors = []
    
    def run(self, duration: int, rate: int):
        """
        Run load test scenario.
        
        Args:
            duration: Test duration in seconds
            rate: Operations per second
        """
        print(f"\nRunning scenario: {self.name}")
        print(f"Duration: {duration}s, Rate: {rate} ops/sec")
        
        start_time = time.time()
        operation_count = 0
        
        while (time.time() - start_time) < duration:
            op_start = time.time()
            
            try:
                self.execute_operation()
                latency = time.time() - op_start
                self.results.append(latency)
                operation_count += 1
            
            except Exception as e:
                self.errors.append(str(e))
            
            # Rate limiting
            sleep_time = (1.0 / rate) - (time.time() - op_start)
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        self.print_results(operation_count)
    
    def execute_operation(self):
        """Override in subclass"""
        raise NotImplementedError
    
    def print_results(self, operation_count: int):
        """Print test results"""
        if not self.results:
            print("❌ No successful operations")
            return
        
        print(f"\n{'='*60}")
        print(f"Results for {self.name}")
        print(f"{'='*60}")
        print(f"Total operations: {operation_count}")
        print(f"Successful: {len(self.results)}")
        print(f"Failed: {len(self.errors)}")
        print(f"Success rate: {len(self.results)/operation_count*100:.2f}%")
        print(f"\nLatency Statistics:")
        print(f"  Min: {min(self.results)*1000:.2f}ms")
        print(f"  Max: {max(self.results)*1000:.2f}ms")
        print(f"  Mean: {statistics.mean(self.results)*1000:.2f}ms")
        print(f"  Median: {statistics.median(self.results)*1000:.2f}ms")
        print(f"  P95: {statistics.quantiles(self.results, n=20)[18]*1000:.2f}ms")
        print(f"  P99: {statistics.quantiles(self.results, n=100)[98]*1000:.2f}ms")
        
        if self.errors:
            print(f"\nFirst 5 errors:")
            for error in self.errors[:5]:
                print(f"  - {error}")


class ValidationLoadTest(LoadTestScenario):
    """Test controller validation load"""
    
    def __init__(self):
        super().__init__("Controller Validation")
        from pdsno.controllers.global_controller import GlobalController
        from pdsno.controllers.context_manager import ContextManager
        from pdsno.datastore import NIBStore
        
        self.gc = GlobalController(
            controller_id="global_cntl_1",
            context_manager=ContextManager("config/context_runtime.yaml"),
            nib_store=NIBStore("config/pdsno.db")
        )
    
    def execute_operation(self):
        """Simulate validation request"""
        # Simulate validation
        temp_id = f"temp-rc-{int(time.time()*1000000)}"
        
        # Bootstrap token verification (mocked)
        valid, error = self.gc.controller_authenticator.verify_bootstrap_token(
            temp_id=temp_id,
            region="zone-A",
            controller_type="regional",
            submitted_token="test_token"
        )


class DiscoveryLoadTest(LoadTestScenario):
    """Test device discovery load"""
    
    def __init__(self, num_devices: int = 100):
        super().__init__(f"Device Discovery ({num_devices} devices)")
        self.num_devices = num_devices
        
        from pdsno.datastore import NIBStore
        self.nib = NIBStore("config/pdsno.db")
    
    def execute_operation(self):
        """Simulate device discovery"""
        from pdsno.datastore.models import Device, DeviceStatus
        
        device_id = f"device-{int(time.time()*1000000)}"
        
        device = Device(
            device_id=device_id,
            temp_scan_id="",
            ip_address=f"192.168.{device_id[-6:-4]}.{device_id[-2:]}",
            mac_address=f"AA:BB:CC:DD:{device_id[-4:-2]}:{device_id[-2:]}",
            hostname=f"test-device-{device_id[-6:]}",
            vendor="cisco",
            device_type="switch",
            status=DeviceStatus.DISCOVERED,
            first_seen=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            managed_by_lc="local_cntl_1",
            region="zone-A",
            metadata={}
        )
        
        self.nib.upsert_device(device)


class ConfigApprovalLoadTest(LoadTestScenario):
    """Test config approval load"""
    
    def __init__(self):
        super().__init__("Config Approval")
        
        from pdsno.datastore import NIBStore
        from pdsno.config.approval_engine import ApprovalWorkflowEngine
        
        self.nib = NIBStore("config/pdsno.db")
        self.approval_engine = ApprovalWorkflowEngine(
            controller_id="local_cntl_1",
            controller_role="local"
        )
    
    def execute_operation(self):
        """Simulate config approval"""
        from pdsno.datastore.models import Config, ConfigStatus
        from pdsno.config.sensitivity_classifier import SensitivityLevel
        
        config_id = f"config-{int(time.time()*1000000)}"
        
        config = Config(
            config_id=config_id,
            device_id="test-device-01",
            config_data='{"lines": ["vlan 100", "name TestVLAN"]}',
            proposed_by="local_cntl_1",
            proposed_at=datetime.now(timezone.utc),
            status=ConfigStatus.PROPOSED
        )
        
        self.nib.upsert_config(config)
        
        # Create and submit approval request
        request = self.approval_engine.create_request(
            device_id="test-device-01",
            config_lines=["vlan 100", "name TestVLAN"],
            sensitivity=SensitivityLevel.LOW
        )
        self.approval_engine.submit_request(request.request_id)


class MessageThroughputTest(LoadTestScenario):
    """Test message bus throughput"""
    
    def __init__(self):
        super().__init__("Message Throughput")
        
        from pdsno.communication.message_bus import MessageBus
        self.message_bus = MessageBus()
        
        # Register dummy handler
        def dummy_handler(envelope):
            pass
        
        self.message_bus.register_controller("test_controller", {
            'TEST': dummy_handler
        })
    
    def execute_operation(self):
        """Send message"""
        from pdsno.communication.message_format import MessageEnvelope, MessageType
        
        envelope = MessageEnvelope(
            message_id=f"msg-{int(time.time()*1000000)}",
            message_type=MessageType.CONFIG_APPROVED,
            sender_id="test_sender",
            recipient_id="test_controller",
            payload={'test': 'data'},
            timestamp=datetime.now(timezone.utc)
        )
        
        self.message_bus.send(envelope)


class ConcurrentLoadTest:
    """Run concurrent load tests"""
    
    def __init__(self, scenario: LoadTestScenario, num_threads: int):
        self.scenario = scenario
        self.num_threads = num_threads
        self.results_queue = queue.Queue()
    
    def run(self, duration: int, rate: int):
        """Run load test with multiple threads"""
        print(f"\nRunning concurrent load test:")
        print(f"Scenario: {self.scenario.name}")
        print(f"Threads: {self.num_threads}")
        print(f"Duration: {duration}s")
        print(f"Rate per thread: {rate} ops/sec")
        print(f"Total rate: {rate * self.num_threads} ops/sec")
        
        threads = []
        
        for i in range(self.num_threads):
            thread = threading.Thread(
                target=self._worker,
                args=(duration, rate)
            )
            thread.start()
            threads.append(thread)
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Aggregate results
        self._aggregate_results()
    
    def _worker(self, duration: int, rate: int):
        """Worker thread"""
        start_time = time.time()
        
        while (time.time() - start_time) < duration:
            op_start = time.time()
            
            try:
                self.scenario.execute_operation()
                latency = time.time() - op_start
                self.results_queue.put(('success', latency))
            except Exception as e:
                self.results_queue.put(('error', str(e)))
            
            # Rate limiting
            sleep_time = (1.0 / rate) - (time.time() - op_start)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def _aggregate_results(self):
        """Aggregate results from all threads"""
        results = []
        errors = []
        
        while not self.results_queue.empty():
            status, data = self.results_queue.get()
            
            if status == 'success':
                results.append(data)
            else:
                errors.append(data)
        
        # Print aggregated results
        self.scenario.results = results
        self.scenario.errors = errors
        self.scenario.print_results(len(results) + len(errors))


def main():
    parser = argparse.ArgumentParser(description='PDSNO Load Testing')
    
    parser.add_argument(
        '--scenario',
        required=True,
        choices=['validation', 'discovery', 'config_approval', 'messages'],
        help='Test scenario to run'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=60,
        help='Test duration in seconds (default: 60)'
    )
    parser.add_argument(
        '--rate',
        type=int,
        default=10,
        help='Operations per second (default: 10)'
    )
    parser.add_argument(
        '--threads',
        type=int,
        default=1,
        help='Number of concurrent threads (default: 1)'
    )
    parser.add_argument(
        '--devices',
        type=int,
        default=100,
        help='Number of devices for discovery test (default: 100)'
    )
    
    args = parser.parse_args()
    
    # Create scenario
    if args.scenario == 'validation':
        scenario = ValidationLoadTest()
    elif args.scenario == 'discovery':
        scenario = DiscoveryLoadTest(args.devices)
    elif args.scenario == 'config_approval':
        scenario = ConfigApprovalLoadTest()
    elif args.scenario == 'messages':
        scenario = MessageThroughputTest()
    
    # Run test
    if args.threads > 1:
        test = ConcurrentLoadTest(scenario, args.threads)
        test.run(args.duration, args.rate)
    else:
        scenario.run(args.duration, args.rate)


if __name__ == "__main__":
    main()