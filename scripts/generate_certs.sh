#!/bin/bash
# Generate TLS Certificates for PDSNO

set -e

CERT_DIR="${CERT_DIR:-/etc/pdsno/certs}"
DAYS="${DAYS:-365}"
COUNTRY="${COUNTRY:-US}"
STATE="${STATE:-California}"
CITY="${CITY:-San Francisco}"
ORG="${ORG:-PDSNO}"

echo "PDSNO Certificate Generator"
echo "============================"
echo "Certificate Directory: $CERT_DIR"
echo "Validity: $DAYS days"
echo

# Create directory
mkdir -p "$CERT_DIR"
cd "$CERT_DIR"

# Generate CA
if [ ! -f ca-key.pem ]; then
    echo "[1/4] Generating Certificate Authority..."
    openssl genrsa -out ca-key.pem 4096
    
    openssl req -new -x509 -days $DAYS -key ca-key.pem \
        -out ca-cert.pem \
        -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/CN=PDSNO-CA"
    
    echo "✓ CA certificate generated"
else
    echo "[1/4] Using existing CA certificate"
fi

# Generate controller key
echo "[2/4] Generating controller private key..."
openssl genrsa -out controller-key.pem 2048

# Generate CSR
echo "[3/4] Generating certificate signing request..."
openssl req -new -key controller-key.pem \
    -out controller-csr.pem \
    -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/CN=controller.pdsno.local"

# Sign with CA
echo "[4/4] Signing certificate..."
openssl x509 -req -days $DAYS \
    -in controller-csr.pem \
    -CA ca-cert.pem \
    -CAkey ca-key.pem \
    -CAcreateserial \
    -out controller-cert.pem

# Set permissions
chmod 600 *.pem
chmod 644 ca-cert.pem controller-cert.pem

# Cleanup
rm controller-csr.pem

echo
echo "✓ Certificates generated successfully!"
echo
echo "Files created:"
echo "  - ca-key.pem          (CA private key - KEEP SECURE)"
echo "  - ca-cert.pem         (CA certificate)"
echo "  - controller-key.pem  (Controller private key)"
echo "  - controller-cert.pem (Controller certificate)"
echo
echo "Usage:"
echo "  python scripts/run_controller.py --enable-tls \\"
echo "    --cert $CERT_DIR/controller-cert.pem \\"
echo "    --key $CERT_DIR/controller-key.pem"