#!/usr/bin/env bash
# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required" >&2
  exit 1
fi

containers=(
  clab-pdsno-distributed-lab-pdsno-gc
  clab-pdsno-distributed-lab-pdsno-rc
  clab-pdsno-distributed-lab-pdsno-lc
)

for c in "${containers[@]}"; do
  if docker ps --format '{{.Names}}' | grep -q "^${c}$"; then
    echo "Following logs for ${c}"
    docker logs -f "$c" 2>&1 | sed -u "s/^/[${c}] /" &
  else
    echo "Skipping ${c} (not running)"
  fi
done

echo "Press Ctrl+C to stop all log followers"
wait
