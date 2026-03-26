#!/usr/bin/env bash
# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

set -euo pipefail

# Stop any background docker log followers started by watch_clab_logs.sh.
pkill -f "docker logs -f clab-pdsno-distributed-lab" || true

echo "Stopped ContainerLab log followers"
