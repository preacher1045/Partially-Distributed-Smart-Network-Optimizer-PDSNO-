#!/bin/bash
# PDSNO Deployment Script

set -e

echo "PDSNO Deployment"
echo "================"

# Check Python
echo "[1/7] Checking Python..."
python3 --version || { echo "Python 3 not found!"; exit 1; }

# Install dependencies
echo "[2/7] Installing dependencies..."
pip3 install -r requirements.txt

# Create directories
echo "[3/7] Creating directories..."
sudo mkdir -p /opt/pdsno/{data,logs,config}
sudo mkdir -p /etc/pdsno/certs
sudo chown -R $USER:$USER /opt/pdsno

# Initialize database
echo "[4/7] Initializing database..."
python3 scripts/init_db.py --db /opt/pdsno/data/pdsno.db

# Generate certificates
echo "[5/7] Generating certificates..."
if [ ! -f /etc/pdsno/certs/controller-cert.pem ]; then
    bash scripts/generate_certs.sh
fi

# Copy config templates
echo "[6/7] Setting up configuration..."
cp config/*.template /opt/pdsno/config/
cd /opt/pdsno/config
for f in *.template; do
    mv "$f" "${f%.template}"
done

# Install systemd service
echo "[7/7] Installing systemd service..."
sudo cp deployment/pdsno-controller.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pdsno-controller

echo
echo "✓ Deployment complete!"
echo
echo "Next steps:"
echo "  1. Edit /opt/pdsno/config/context_runtime.yaml"
echo "  2. Generate bootstrap token: python3 scripts/generate_bootstrap_token.py"
echo "  3. Start controller: sudo systemctl start pdsno-controller"
echo "  4. Check status: sudo systemctl status pdsno-controller"