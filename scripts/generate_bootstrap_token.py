#!/usr/bin/env python3
"""
Generate Bootstrap Token

Creates HMAC-signed bootstrap tokens for controller validation.

Bootstrap tokens are single-use secrets that prove a controller was
legitimately provisioned. They're used in Step 2 of the validation flow.

Usage:
    # Generate token for Regional Controller
    python scripts/generate_bootstrap_token.py --region zone-A --type regional
    
    # Generate token for Local Controller
    python scripts/generate_bootstrap_token.py --region zone-B --type local
    
    # Use custom secret file
    python scripts/generate_bootstrap_token.py --region zone-A --type regional --secret-file /secure/bootstrap.key
    
    # Generate multiple tokens
    python scripts/generate_bootstrap_token.py --region zone-A --type local --count 5
"""

import argparse
import hmac
import hashlib
import secrets
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_or_generate_secret(secret_file: str) -> bytes:
    """
    Load bootstrap secret from file or generate new one.
    
    Args:
        secret_file: Path to secret file
    
    Returns:
        32-byte secret
    """
    secret_path = Path(secret_file)
    
    try:
        with open(secret_path, 'rb') as f:
            secret = f.read()
        
        if len(secret) < 32:
            raise ValueError(f"Secret file {secret_file} is too short (need 32 bytes)")
        
        print(f"✓ Loaded bootstrap secret from {secret_file}")
        return secret[:32]  # Use first 32 bytes
    
    except FileNotFoundError:
        print(f"Bootstrap secret not found at {secret_file}")
        print("Generating new bootstrap secret...")
        
        secret = secrets.token_bytes(32)
        
        # Ensure directory exists
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save secret
        with open(secret_path, 'wb') as f:
            f.write(secret)
        
        # Set restrictive permissions
        secret_path.chmod(0o600)
        
        print(f"✓ Secret saved to {secret_file}")
        print(f"⚠️  IMPORTANT: Backup this file securely!")
        
        return secret


def generate_token(
    temp_id: str,
    region: str,
    controller_type: str,
    secret: bytes
) -> str:
    """
    Generate HMAC-SHA256 bootstrap token.
    
    Args:
        temp_id: Temporary controller ID
        region: Region name
        controller_type: "regional" or "local"
        secret: Bootstrap secret
    
    Returns:
        Hex-encoded token
    """
    # Token input format: temp_id|region|type
    token_input = f"{temp_id}|{region}|{controller_type}".encode()
    
    # Compute HMAC-SHA256
    token = hmac.new(secret, token_input, hashlib.sha256).hexdigest()
    
    return token


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Generate Bootstrap Token for Controller Validation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--region',
        required=True,
        help='Region name (e.g., zone-A, east-coast-1)'
    )
    parser.add_argument(
        '--type',
        required=True,
        choices=['regional', 'local'],
        help='Controller type'
    )
    parser.add_argument(
        '--temp-id',
        help='Custom temporary ID (auto-generated if not provided)'
    )
    parser.add_argument(
        '--secret-file',
        default='config/bootstrap_secret.key',
        help='Bootstrap secret file (default: config/bootstrap_secret.key)'
    )
    parser.add_argument(
        '--count',
        type=int,
        default=1,
        help='Number of tokens to generate (default: 1)'
    )
    parser.add_argument(
        '--output',
        help='Output file for tokens (prints to stdout if not specified)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output in JSON format'
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()
    
    # Load or generate secret
    try:
        secret = load_or_generate_secret(args.secret_file)
    except Exception as e:
        print(f"\n✗ Error loading secret: {e}")
        sys.exit(1)
    
    # Generate tokens
    tokens = []
    
    for i in range(args.count):
        # Generate temp ID
        if args.temp_id:
            temp_id = f"{args.temp_id}-{i+1}" if args.count > 1 else args.temp_id
        else:
            temp_id = f"temp-{args.type[:2]}-{args.region}-{secrets.token_hex(4)}"
        
        # Generate token
        token = generate_token(temp_id, args.region, args.type, secret)
        
        tokens.append({
            'temp_id': temp_id,
            'region': args.region,
            'type': args.type,
            'token': token,
            'generated_at': datetime.now(timezone.utc).isoformat()
        })
    
    # Output tokens
    if args.json:
        import json
        output = json.dumps(tokens, indent=2)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"✓ Tokens written to {args.output}")
        else:
            print(output)
    
    else:
        # Human-readable format
        print("\n" + "="*70)
        print("Bootstrap Tokens Generated")
        print("="*70)
        
        for token_data in tokens:
            print(f"\nTemp ID:   {token_data['temp_id']}")
            print(f"Region:    {token_data['region']}")
            print(f"Type:      {token_data['type']}")
            print(f"Token:     {token_data['token']}")
            print(f"Generated: {token_data['generated_at']}")
            print("-" * 70)
        
        print("\nUsage:")
        print(f"  python scripts/run_controller.py \\")
        print(f"    --type {args.type} \\")
        print(f"    --region {args.region} \\")
        print(f"    --id {tokens[0]['temp_id']} \\")
        print(f"    --parent <parent_controller_id>")
        print("\n" + "="*70)
        
        if args.output:
            with open(args.output, 'w') as f:
                for token_data in tokens:
                    f.write(f"# {token_data['type']} controller in {token_data['region']}\n")
                    f.write(f"TEMP_ID={token_data['temp_id']}\n")
                    f.write(f"BOOTSTRAP_TOKEN={token_data['token']}\n\n")
            print(f"\n✓ Tokens also written to {args.output}")
    
    print(f"\n⚠️  Security Reminders:")
    print(f"  - Tokens are single-use")
    print(f"  - Keep bootstrap secret secure")
    print(f"  - Rotate secret periodically")
    print(f"  - Use TLS in production")


if __name__ == "__main__":
    main()