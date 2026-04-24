#!/usr/bin/env python3

# Copyright (C) 2025 TENKEI
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This file is part of PDSNO.
# See the LICENSE file in the project root for license information.

"""
RBAC Policy Check

Validates expected RBAC roles and permissions and optionally validates
role bindings declared in a policy YAML file.

Usage:
  python scripts/check_rbac.py
  python scripts/check_rbac.py --policy config/policy_default.yaml.template
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List

import yaml

from pdsno.security.rbac import RBACManager, Role, Resource, Action


REQUIRED_ROLES = [
    Role.GLOBAL_CONTROLLER,
    Role.REGIONAL_CONTROLLER,
    Role.LOCAL_CONTROLLER,
    Role.GLOBAL_ADMIN,
    Role.REGIONAL_ADMIN,
    Role.LOCAL_OPERATOR,
    Role.VIEWER,
    Role.API_CLIENT,
    Role.API_CLIENT_READONLY,
]


def _load_policy(path: Path) -> Dict:
    if not path.exists():
        raise FileNotFoundError(f"Policy file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data


def _validate_default_roles(rbac: RBACManager) -> List[str]:
    errors: List[str] = []

    for role in REQUIRED_ROLES:
        if role not in rbac.roles:
            errors.append(f"Missing role definition: {role.value}")
            continue
        if not rbac.roles[role].permissions:
            errors.append(f"Role has no permissions: {role.value}")

    return errors


def _validate_role_semantics(rbac: RBACManager) -> List[str]:
    errors: List[str] = []

    # Assign roles to synthetic entity IDs for checks.
    rbac.assign_role("gc", Role.GLOBAL_CONTROLLER)
    rbac.assign_role("rc", Role.REGIONAL_CONTROLLER)
    rbac.assign_role("lc", Role.LOCAL_CONTROLLER)
    rbac.assign_role("api_ro", Role.API_CLIENT_READONLY)

    if not rbac.can_approve_config("gc", "HIGH"):
        errors.append("GLOBAL_CONTROLLER cannot approve HIGH configs")

    if rbac.can_approve_config("rc", "HIGH"):
        errors.append("REGIONAL_CONTROLLER should not approve HIGH configs")

    if not rbac.check_permission("lc", Resource.CONFIG, Action.EXECUTE):
        errors.append("LOCAL_CONTROLLER cannot execute configs")

    if rbac.check_permission("api_ro", Resource.CONFIG, Action.CREATE):
        errors.append("API_CLIENT_READONLY should not create configs")

    return errors


def _validate_policy_bindings(policy: Dict, rbac: RBACManager) -> List[str]:
    errors: List[str] = []

    rbac_block = policy.get("rbac")
    if not rbac_block:
        return errors

    roles_node = rbac_block.get("roles")
    if roles_node:
        if isinstance(roles_node, dict):
            role_names = list(roles_node.keys())
        elif isinstance(roles_node, list):
            role_names = roles_node
        else:
            errors.append("rbac.roles must be a list or mapping")
            role_names = []

        for role_name in role_names:
            try:
                Role(role_name)
            except ValueError:
                errors.append(f"Unknown role in policy: {role_name}")

    assignments = rbac_block.get("assignments")
    if assignments:
        if not isinstance(assignments, dict):
            errors.append("rbac.assignments must be a mapping of entity -> role")
        else:
            for entity_id, role_name in assignments.items():
                try:
                    role = Role(role_name)
                except ValueError:
                    errors.append(
                        f"Unknown role '{role_name}' assigned to {entity_id}"
                    )
                    continue
                rbac.assign_role(entity_id, role)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RBAC policy setup")
    parser.add_argument(
        "--policy",
        default="config/policy_default.yaml.template",
        help="Policy YAML path",
    )

    args = parser.parse_args()

    print("PDSNO RBAC Check")
    print("=" * 60)

    rbac = RBACManager()
    errors: List[str] = []

    # Load policy if present.
    policy_path = Path(args.policy)
    policy = {}
    try:
        policy = _load_policy(policy_path)
        print(f"Policy file: {policy_path}")
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    errors.extend(_validate_default_roles(rbac))
    errors.extend(_validate_role_semantics(rbac))
    errors.extend(_validate_policy_bindings(policy, rbac))

    if errors:
        print("\nRBAC validation failed:")
        for item in errors:
            print(f"  - {item}")
        return 1

    if "rbac" not in policy:
        print("\nWarning: policy file has no rbac section; using defaults")

    print("\n✓ RBAC validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
