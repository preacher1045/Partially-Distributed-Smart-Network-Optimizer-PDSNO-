#!/bin/bash
# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Deploy PDSNO distributed lab and fix post-deploy permissions.
# Usage: bash scripts/deploy_lab.sh

set -e

TOPOLOGY="containerlab/topologies/pdsno-distributed-lab.yml"
DB_PATH="sim_distributed/pdsno.db"

echo "Deploying lab..."
sudo containerlab deploy -t "$TOPOLOGY"

echo "Waiting 45s for controllers to initialize and complete first discovery..."
sleep 45

echo "Fixing database permissions..."
sudo chown "$USER:$USER" "$DB_PATH"

echo ""
echo "Lab deployed. Verify with:"
echo "  curl -s http://172.20.20.5:8001/health | python3 -m json.tool"
echo "  curl -s http://172.20.20.6:8002/health | python3 -m json.tool"
echo "  PDSNO_LIVE_LAB=1 python -m pytest tests/test_live.py -v -s"
