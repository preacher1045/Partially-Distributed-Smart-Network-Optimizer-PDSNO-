#!/usr/bin/env python3
"""
PDSNO Controller Runner

Start Global, Regional, or Local Controller with proper configuration.

Usage:
    # Global Controller
    python scripts/run_controller.py --type global --port 8001
    
    # Regional Controller
    python scripts/run_controller.py --type regional --region zone-A --parent global_cntl_1
    
    # Local Controller
    python scripts/run_controller.py --type local --region zone-A --parent regional_cntl_zone-A_1 --subnet 192.168.1.0/24

Examples:
    # Start Global Controller with TLS
    python scripts/run_controller.py --type global --port 8001 --enable-tls --cert /etc/pdsno/certs/controller-cert.pem --key /etc/pdsno/certs/controller-key.pem
    
    # Start Regional Controller
    python scripts/run_controller.py --type regional --region zone-A --parent global_cntl_1 --port 8002
    
    # Start Local Controller with discovery
    python scripts/run_controller.py --type local --region zone-A --parent regional_cntl_zone-A_1 --subnet 192.168.1.0/24 --discovery-interval 300
"""

import argparse
import logging
import sys
from pathlib import Path
import signal
import yaml
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pdsno.controllers.global_controller import GlobalController
from pdsno.controllers.regional_controller import RegionalController
from pdsno.controllers.local_controller import LocalController
from pdsno.controllers.context_manager import ContextManager
from pdsno.datastore import NIBStore
from pdsno.communication.message_bus import MessageBus


def setup_logging(level=logging.INFO):
    """Configure logging"""
    handlers = [logging.StreamHandler()]
    
    # Try to add file handler, fall back to console only
    log_file = os.getenv('PDSNO_LOG_FILE', '/var/log/pdsno/controller.log')
    
    try:
        # Ensure directory exists
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    except (PermissionError, OSError) as e:
        print(f"Warning: Cannot write to log file {log_file}: {e}")
        print("Logging to console only")
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='PDSNO Controller Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Required arguments
    parser.add_argument(
        '--type',
        required=True,
        choices=['global', 'regional', 'local'],
        help='Controller type'
    )
    
    # Controller identification
    parser.add_argument(
        '--id',
        help='Controller ID (auto-generated if not provided)'
    )
    parser.add_argument(
        '--region',
        help='Region name (required for regional/local)'
    )
    parser.add_argument(
        '--parent',
        help='Parent controller ID (required for regional/local)'
    )
    
    # Network configuration
    parser.add_argument(
        '--port',
        type=int,
        default=8001,
        help='REST API port (default: 8001)'
    )
    parser.add_argument(
        '--mqtt-broker',
        default='localhost',
        help='MQTT broker host (default: localhost)'
    )
    parser.add_argument(
        '--mqtt-port',
        type=int,
        default=1883,
        help='MQTT broker port (default: 1883)'
    )
    
    # TLS configuration
    parser.add_argument(
        '--enable-tls',
        action='store_true',
        help='Enable TLS for REST and MQTT'
    )
    parser.add_argument(
        '--cert',
        help='TLS certificate path'
    )
    parser.add_argument(
        '--key',
        help='TLS private key path'
    )
    parser.add_argument(
        '--ca-cert',
        help='CA certificate path'
    )
    
    # Storage configuration
    parser.add_argument(
        '--config',
        default='config/context_runtime.yaml',
        help='Context configuration file (default: config/context_runtime.yaml)'
    )
    parser.add_argument(
        '--db',
        default='config/pdsno.db',
        help='NIB database path (default: config/pdsno.db)'
    )
    
    # Local controller specific
    parser.add_argument(
        '--subnet',
        help='Subnet to discover (CIDR notation, e.g., 192.168.1.0/24)'
    )
    parser.add_argument(
        '--discovery-interval',
        type=int,
        default=300,
        help='Discovery interval in seconds (default: 300)'
    )
    
    # Operational
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--no-validation',
        action='store_true',
        help='Skip validation with parent (for testing only)'
    )
    
    return parser.parse_args()


def validate_args(args):
    """Validate argument combinations"""
    errors = []
    
    # Regional/Local controllers need region and parent
    if args.type in ['regional', 'local']:
        if not args.region:
            errors.append(f"{args.type} controller requires --region")
        if not args.parent and not args.no_validation:
            errors.append(f"{args.type} controller requires --parent")
    
    # Local controller needs subnet for discovery
    if args.type == 'local' and not args.subnet:
        errors.append("local controller requires --subnet for discovery")
    
    # TLS requires cert and key
    if args.enable_tls:
        if not args.cert or not args.key:
            errors.append("TLS requires both --cert and --key")
    
    if errors:
        print("Error: Invalid arguments\n")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)


def create_controller(args):
    """Create appropriate controller instance"""
    
    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(log_level)
    
    logger = logging.getLogger(__name__)
    
    # Initialize infrastructure
    logger.info("Initializing PDSNO infrastructure...")
    
    try:
        context_mgr = ContextManager(args.config)
    except FileNotFoundError:
        print(f"Error: Configuration file not found: {args.config}")
        print("Create it with: cp config/context_runtime.yaml.template {args.config}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML in configuration file: {e}")
        sys.exit(1)
        
    nib_store = NIBStore(args.db)
    message_bus = MessageBus()
    
    # Create controller based on type
    if args.type == 'global':
        logger.info("Creating Global Controller...")
        
        controller_id = args.id or "global_cntl_1"
        
        controller = GlobalController(
            controller_id=controller_id,
            context_manager=context_mgr,
            nib_store=nib_store,
            message_bus=message_bus,
            rest_port=args.port,
            enable_rest=True,
            enable_tls=args.enable_tls,
            cert_file=args.cert,
            key_file=args.key
        )
        
        logger.info(f"✓ Global Controller {controller_id} initialized")
    
    elif args.type == 'regional':
        logger.info(f"Creating Regional Controller for region {args.region}...")
        
        temp_id = args.id or f"temp-rc-{args.region}"
        
        controller = RegionalController(
            temp_id=temp_id,
            region=args.region,
            context_manager=context_mgr,
            nib_store=nib_store,
            message_bus=message_bus,
            enable_rest=True,
            rest_port=args.port,
            enable_tls=args.enable_tls,
            cert_file=args.cert,
            key_file=args.key
        )
        
        # Request validation from parent
        if not args.no_validation:
            logger.info(f"Requesting validation from {args.parent}...")
            controller.request_validation(args.parent)
            
            if controller.validated:
                logger.info(f"✓ Validated! Assigned ID: {controller.assigned_id}")
            else:
                logger.error("✗ Validation failed")
                sys.exit(1)
        
        logger.info(f"✓ Regional Controller initialized")
    
    elif args.type == 'local':
        logger.info(f"Creating Local Controller for region {args.region}...")
        
        temp_id = args.id or f"temp-lc-{args.region}"
        
        controller = LocalController(
            temp_id=temp_id,
            region=args.region,
            subnet=args.subnet,
            context_manager=context_mgr,
            nib_store=nib_store,
            message_bus=message_bus,
            discovery_interval=args.discovery_interval
        )
        
        # Request validation from parent
        if not args.no_validation:
            logger.info(f"Requesting validation from {args.parent}...")
            controller.request_validation(args.parent)
            
            if controller.validated:
                logger.info(f"✓ Validated! Assigned ID: {controller.assigned_id}")
            else:
                logger.error("✗ Validation failed")
                sys.exit(1)
        
        logger.info(f"✓ Local Controller initialized")
    
    return controller


def main():
    """Main entry point"""
    args = parse_args()
    validate_args(args)
    
    print("\n" + "="*70)
    print("PDSNO Controller Runner")
    print("="*70)
    print(f"Type:     {args.type.upper()}")
    print(f"Region:   {args.region or 'N/A'}")
    print(f"Port:     {args.port}")
    print(f"TLS:      {'Enabled' if args.enable_tls else 'Disabled'}")
    print(f"Database: {args.db}")
    print("="*70)
    print()
    
    # Create controller
    try:
        controller = create_controller(args)
    except Exception as e:
        print(f"\n✗ Error creating controller: {e}")
        sys.exit(1)
    
    # Setup signal handlers
    def signal_handler(signum, frame):
        print("\n\nShutting down gracefully...")
        controller.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start controller
    print(f"Starting {args.type.upper()} Controller...")
    print(f"REST API: http{'s' if args.enable_tls else ''}://0.0.0.0:{args.port}")
    print(f"Health:   http{'s' if args.enable_tls else ''}://0.0.0.0:{args.port}/health")
    print(f"Metrics:  http://0.0.0.0:9090/metrics")
    print("\nPress Ctrl+C to stop\n")
    
    try:
        controller.run()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        controller.shutdown()
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()