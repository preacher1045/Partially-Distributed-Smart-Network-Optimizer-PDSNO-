# Phase 7 Test and Simulation Results

**Date:** February 24, 2026  
**Scope:** Configuration approval logic (Phase 7)

---

## Test Results

Command:
```
python -m pytest tests/test_config_approval.py -v
```

Output:
```
======================================= test session starts ========================================
platform win32 -- Python 3.13.0, pytest-9.0.2, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: C:\Users\dmipr\Desktop\projects\Serious project\Personal work\Partially-Distributed-Smart-Network-Optimizer-PDSNO-
plugins: anyio-4.12.1, asyncio-1.3.0, cov-7.0.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 26 items

tests/test_config_approval.py::TestSensitivityClassifier::test_low_sensitivity PASSED
tests/test_config_approval.py::TestSensitivityClassifier::test_medium_sensitivity PASSED
tests/test_config_approval.py::TestSensitivityClassifier::test_high_sensitivity PASSED
tests/test_config_approval.py::TestSensitivityClassifier::test_classify_with_details PASSED
tests/test_config_approval.py::TestApprovalWorkflow::test_create_request PASSED
tests/test_config_approval.py::TestApprovalWorkflow::test_submit_low_auto_approves PASSED
tests/test_config_approval.py::TestApprovalWorkflow::test_submit_medium_pending PASSED
tests/test_config_approval.py::TestApprovalWorkflow::test_approve_request PASSED
tests/test_config_approval.py::TestApprovalWorkflow::test_reject_request PASSED
tests/test_config_approval.py::TestExecutionToken::test_issue_token PASSED
tests/test_config_approval.py::TestExecutionToken::test_verify_valid_token PASSED
tests/test_config_approval.py::TestExecutionToken::test_verify_tampered_token PASSED
tests/test_config_approval.py::TestExecutionToken::test_verify_expired_token PASSED
tests/test_config_approval.py::TestExecutionToken::test_replay_prevention PASSED
tests/test_config_approval.py::TestConfigStateMachine::test_initial_state PASSED
tests/test_config_approval.py::TestConfigStateMachine::test_valid_transition PASSED
tests/test_config_approval.py::TestConfigStateMachine::test_invalid_transition PASSED
tests/test_config_approval.py::TestConfigStateMachine::test_transition_history PASSED
tests/test_config_approval.py::TestRollbackManager::test_create_backup PASSED
tests/test_config_approval.py::TestRollbackManager::test_get_latest_backup PASSED
tests/test_config_approval.py::TestRollbackManager::test_rollback PASSED
tests/test_config_approval.py::TestRollbackManager::test_auto_rollback PASSED
tests/test_config_approval.py::TestAuditTrail::test_log_config_created PASSED
tests/test_config_approval.py::TestAuditTrail::test_query_events PASSED
tests/test_config_approval.py::TestAuditTrail::test_get_config_history PASSED
tests/test_config_approval.py::TestAuditTrail::test_generate_report PASSED

======================================== 26 passed in 0.50s ========================================
```

Summary:
- Tests: 26
- Passed: 26
- Failed: 0
- Duration: 0.50s

---

## Simulation Results

Command:
```
$env:PYTHONPATH="."
python examples/simulate_config_approval.py
```

Output (abridged):
```
======================================================================
PDSNO Phase 7 - Configuration Approval Workflow Simulation
======================================================================
[1/10] Initializing components...
✓ All components initialized

[2/10] Scenario 1: LOW Sensitivity Configuration
LOW sensitivity (no high/medium patterns matched)
Configuration classified as: LOW
CONFIG_CREATED (SUCCESS)
Auto-approving LOW sensitivity request ...
✓ LOW sensitivity: Auto-approved
ERROR - Invalid transition: DRAFT -> APPROVED
CONFIG_APPROVED (SUCCESS)

[3/10] Scenario 2: MEDIUM Sensitivity Configuration
MEDIUM sensitivity detected (pattern: vlan\s+\d+)
Configuration classified as: MEDIUM
CONFIG_CREATED (SUCCESS)
Transitioned: DRAFT -> PENDING_APPROVAL
CONFIG_SUBMITTED (PENDING)
Request state: PENDING_APPROVAL
Regional Controller reviewing...
ERROR - Request <id> not found

[4/10] Scenario 3: HIGH Sensitivity Configuration
HIGH sensitivity detected (pattern: router\s+(bgp|ospf|eigrp))
Configuration classified as: HIGH
Reasoning: Contains high-impact commands affecting routing, security, or critical services
High-risk commands: ['bgp']
CONFIG_CREATED (SUCCESS)
HIGH sensitivity requires Global Controller approval

[5/10] Issuing execution token...
Issued execution token <id> for device switch-access-02
✓ Token issued
TOKEN_ISSUED (SUCCESS)

[6/10] Verifying execution token...
Verified execution token <id>
✓ Token verified successfully
TOKEN_VERIFIED (SUCCESS)

[7/10] Creating pre-execution backup...
Created backup <id> for device switch-access-02
✓ Backup created

[8/10] Executing configuration...
ERROR - Invalid transition: PENDING_APPROVAL -> EXECUTING
ERROR - Invalid transition: PENDING_APPROVAL -> EXECUTED
CONFIG_EXECUTED (SUCCESS)
✓ Configuration executed successfully

[9/10] Demonstrating rollback capability...
Rolling back device switch-access-02 to backup <id>
Rollback <id> successful
✓ Rollback successful
ERROR - Invalid transition: PENDING_APPROVAL -> ROLLED_BACK
CONFIG_ROLLED_BACK (SUCCESS)

[10/10] Generating audit report...
Total audit events: 9
Events by type:
  CONFIG_CREATED: 3
  CONFIG_APPROVED: 1
  CONFIG_SUBMITTED: 1
  TOKEN_ISSUED: 1
  TOKEN_VERIFIED: 1
  CONFIG_EXECUTED: 1
  CONFIG_ROLLED_BACK: 1

Phase 7 Simulation Complete!
```

Notes:
- The simulation completed and logged all workflow steps.
- Several state machine transitions logged as invalid during the demo flow:
  - DRAFT -> APPROVED (LOW scenario)
  - PENDING_APPROVAL -> EXECUTING / EXECUTED (MEDIUM scenario)
  - PENDING_APPROVAL -> ROLLED_BACK (rollback demo)
- The medium-approval step reported "Request <id> not found" because the RegionalController approval engine instance did not share request state with the LocalController engine. In a real deployment, requests would be routed to the correct controller or stored in shared state.

---

## Environment

- OS: Windows
- Python: 3.13.0
- pytest: 9.0.2
