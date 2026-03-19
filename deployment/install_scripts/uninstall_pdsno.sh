#!/bin/bash

# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

# Uninstall PDSNO

set -e

PDSNO_HOME="${PDSNO_HOME:-/opt/pdsno}"
PDSNO_USER="${PDSNO_USER:-pdsno}"

echo "WARNING: This will remove PDSNO completely!"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Uninstall cancelled"
    exit 0
fi

# Stop service
systemctl stop pdsno-controller || true
systemctl disable pdsno-controller || true

# Remove service file
rm -f /etc/systemd/system/pdsno-controller.service
systemctl daemon-reload

# Remove installation
rm -rf "$PDSNO_HOME"
rm -rf /etc/pdsno

# Remove user
userdel -r "$PDSNO_USER" || true

echo "✓ PDSNO uninstalled"