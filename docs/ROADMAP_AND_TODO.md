# PDSNO — Master Roadmap & Development TODO

> **This document is the authoritative guide for all development activity on PDSNO.**
> Every task, decision, and milestone is tracked here. Update it as work progresses.

**Last Updated:** February 2026
**Current Phase:** Phase 0 — Documentation Completion & Architecture Hardening
**Next Milestone:** Phase 1 — Proof of Concept (Core Controller Skeleton)

### Project Parameters (Confirmed)

| Parameter | Decision |
|-----------|----------|
| **v1 Definition** | Proof of concept — demonstrates the architecture works end-to-end |
| **Implementation Language** | Python (learning as we go — tasks are broken into teachable steps) |
| **Timeline** | Self-paced, no external deadline |
| **Approach** | Build it properly and systematically, quality over speed |

> **A note on the Python tasks:** Because we are learning Python alongside building PDSNO, every implementation task in Phase 1 onward includes a "What you need to know first" note. These are not prerequisites you need to master before starting — they are concepts to study *as* you work on that specific task. We tackle one concept at a time.

---

## How to Use This Document

Tasks are organized into **phases**. Each phase must be substantially complete before the next begins — this is intentional. Skipping phases creates technical debt that compounds badly in distributed systems.

Each task has a status tag:

| Tag | Meaning |
|-----|---------|
| `[ ]` | Not started |
| `[~]` | In progress |
| `[x]` | Complete |
| `[!]` | Blocked — needs a decision or dependency resolved first |

---

## Phase 0 — Documentation Completion & Architecture Hardening

> **Goal:** Every architectural decision is written down, unambiguous, and internally consistent before a single line of production code is written. This phase is the foundation everything else stands on.

### 0.1 — Fix Existing Documentation

- `[~]` **Rewrite `PROJECT_OVERVIEW.md`** — Clean up language, resolve the "partially decentralized" vs "centralized root of trust" tension explicitly
- `[~]` **Rewrite `README.md`** — More concise, contributor-friendly, accurate status badges
- `[~]` **Rewrite `algorithm_lifecycle.md`** — Fix base class signature inconsistency (`execute()` has no params but depends on state from `initialize()`), add thread-safety note
- `[~]` **Rewrite `controller_validation_sequence.md`** — Add atomicity requirement for cert issuance + context write; clarify what happens on partial failure
- `[~]` **Consolidate approval logic docs** — Three documents currently cover the same system (`config_approval_doc.md`, `policy_propagation_doc.md`, `config_approval_logic.md`). Restructure into: one canonical spec + one pseudocode/algorithm doc
- `[~]` **Rewrite `threat_model.md`** — Add T10: Compromised Global Controller scenario; explicitly state what is out of scope for v1 and why
- `[~]` **Rewrite `device_discovery_sequence.md`** — Elevate from brainstorming notes to a proper design document

### 0.2 — Fill Empty Documents

- `[ ]` **Write `docs/architecture.md`** — High-level architecture narrative; the document a new engineer reads first. Should cover: four-layer model, controller hierarchy, data flow directions, key design decisions and *why* they were made
- `[~]` **Write `docs/security_model.md`** — Consolidated security posture document covering: trust hierarchy, cryptographic assumptions, key management lifecycle, what the system does/does not protect against
- `[~]` **Write `docs/dataflow.md`** — Trace data from a network event all the way through LC → RC → GC → NIB → back down. Covers both control plane and data plane flows
- `[~]` **Write `docs/api_reference.md`** — Define all inter-controller message types, their fields, and validation rules. This becomes the contract between components
- `[~]` **Write `docs/deployment_guide.md`** — How to stand up a minimal PDSNO environment (single GC, one RC, one LC) for development and testing
- `[~]` **Write `docs/use_cases.md`** — Concrete scenarios with step-by-step traces through the system (device discovery, config approval, controller validation, emergency response)

### 0.3 — Create New Documents for Architecture Gaps

- `[x]` **Write `docs/architecture/nib/nib_spec.md`** — Complete. Includes two-tier data classification (Onix), adaptive consistency model (Alsheikh et al. 2024), typed entity hierarchy, ONF interface naming. Research-grounded.

- `[x]` **Write `docs/architecture/nib/nib_consistency.md`** — Deep-dive on the distributed consistency problem. Now has clear direction: optimistic locking for PoC, adaptive consistency for Phase 6+.

- `[x]` **Write `docs/architecture/controller_hierarchy.md`** — Dedicated document for the controller model. Must include the explicit hierarchy-vs-performance tradeoff note (added to `PROJECT_OVERVIEW.md` but needs its own section here).

- `[ ]` **Write `docs/architecture/verification/key_management.md`** *(Phase 6 — deferred)* — How keys are generated, distributed, rotated, and revoked. HMAC shared secret for PoC; Ed25519 asymmetric for Phase 6+.

- `[x]` **Write `docs/architecture/communication_model.md`** — Complete. Covers REST/MQTT split (research-validated), delta-sync principle (DISCO), ONF interface naming, message envelope format, authentication, timeout/retry contracts.

- `[x]` **Write `CONTRIBUTING.md`** — Proper contributor guide covering setup, coding standards, tests, PR requirements, architecture review checklist.

### 0.4 — Structural & Cross-Cutting Fixes

- `[ ]` **Standardize document headers** — Every `.md` file should have consistent frontmatter: `title`, `status`, `author`, `last_updated`, `component`, `depends_on`
- `[ ]` **Add a `depends_on` field to all docs** — Makes it explicit which documents a reader must understand before reading a given doc
- `[x]` **Create a documentation index** — `docs/INDEX.md` now maps canonical docs, reading paths, and archive boundaries.
- `[x]` **Audit all cross-references** — Corrected key stale links and path mismatches in onboarding and architecture docs.
- `[ ]` **Resolve "partially decentralized" naming consistently** — Either rename the project or update all docs to accurately explain what "partial" means in practice

---

## Phase 1 — Project Foundation & Python Basics

> **Goal:** A working Python project structure with a virtual environment, folder layout matching the architecture, a passing test, and a working logger. No controller logic yet — just making sure the foundation is solid before building on it.
>
> **What "done" looks like:** You can type `python -m pytest` and see green. You can run a script that imports from the project and logs a structured message. Everything else depends on this being right.
>
> **Entry Requirement:** Phase 0 sections 0.1 and the NIB spec (0.3) must be complete.

### 1.1 — Environment Setup

> 📖 *What to study first:* Python virtual environments (`venv`), what `pip` does, why we isolate dependencies per project. This is one hour of reading, not a deep topic.

- `[ ]` Install Python 3.11+ and confirm with `python --version`
- `[ ]` Create a virtual environment in the project root: `python -m venv .venv`
- `[ ]` Understand how to activate it (`source .venv/bin/activate` on Mac/Linux, `.venv\Scripts\activate` on Windows) — add a note in `docs/deployment_guide.md` so you never forget
- `[ ]` Create `requirements.txt` with the first two dependencies: `pytest` and `pyyaml`
- `[ ]` Install them: `pip install -r requirements.txt`

### 1.2 — Folder Structure

> 📖 *What to study first:* Python packages vs modules — specifically, what `__init__.py` does and why it matters for imports. This is a 20-minute topic but it will save you hours of confusing import errors.

- `[ ]` Create the following folder structure exactly as shown:
  ```
  pdsno/
  ├── __init__.py
  ├── base/
  │   └── __init__.py
  ├── controllers/
  │   └── __init__.py
  ├── algorithms/
  │   └── __init__.py
  ├── data/
  │   └── __init__.py
  ├── communication/
  │   └── __init__.py
  tests/
  ├── __init__.py
  └── test_placeholder.py
  config/
  └── context_runtime.yaml
  ```
- `[ ]` Write a single placeholder test in `test_placeholder.py`:
  ```python
  def test_project_imports():
      import pdsno
      assert pdsno is not None
  ```
- `[ ]` Run `python -m pytest` from the project root and confirm it passes — if it doesn't, fix it before moving on

### 1.3 — Logging Framework

> 📖 *What to study first:* Python's built-in `logging` module — specifically `getLogger`, log levels (DEBUG/INFO/WARNING/ERROR), and how to add a custom formatter. Structured (JSON) logging is what production systems use and we want good habits from the start.

- `[ ]` Create `pdsno/utils/logger.py` — a single function `get_logger(name)` that returns a logger configured with a JSON formatter
- `[ ]` Every log entry must include at minimum: `timestamp`, `level`, `controller_id` (can be `"system"` for now), `message`
- `[ ]` Write a test that calls `get_logger` and confirms it returns a logger without raising an error
- `[ ]` Use this logger in every file from this point forward — no bare `print()` statements in production code

---

## Phase 2 — Base Classes

> **Goal:** Implement the three foundational classes that everything else in PDSNO inherits from: `AlgorithmBase`, `BaseController`, and `ContextManager`. These are not complex — but they must be designed carefully because every other component depends on them.
>
> **What "done" looks like:** You can write a toy algorithm that inherits `AlgorithmBase`, run it through `initialize → execute → finalize`, and see the result. You can read and write `context_runtime.yaml` safely through `ContextManager`.
>
> **Entry Requirement:** Phase 1 complete.

### 2.1 — AlgorithmBase

> 📖 *What to study first:* Python classes, inheritance, and abstract base classes (`abc` module — specifically `ABC` and `abstractmethod`). Also read about instance variables (`self.something`) — this is how `initialize()` passes state to `execute()`.

- `[ ]` Create `pdsno/base/algorithm_base.py` implementing `AlgorithmBase` exactly as specified in `docs/algorithm_lifecycle.md`
- `[ ]` Use `@abstractmethod` decorators so Python will raise an error if a subclass forgets to implement a method
- `[ ]` Add a `_initialized` flag: `execute()` should raise `RuntimeError("initialize() must be called before execute()")` if called before `initialize()`
- `[ ]` Write a concrete test subclass inside `tests/test_algorithm_base.py` — not a real algorithm, just a `DummyAlgorithm` that stores a value in `initialize` and returns it in `execute`
- `[ ]` Write tests for: normal lifecycle, calling `execute` before `initialize` (should raise), calling `finalize` before `execute` (should raise)

### 2.2 — ContextManager

> 📖 *What to study first:* Reading and writing YAML files in Python (`pyyaml` library — `yaml.safe_load` and `yaml.dump`). Then read about file locking — specifically Python's `fcntl` module on Linux/Mac or `msvcrt` on Windows, or better yet the `filelock` library which handles both. File locking prevents two processes writing the same file simultaneously.

- `[ ]` Add `filelock` to `requirements.txt` and install it
- `[ ]` Create `pdsno/data/context_manager.py` with a `ContextManager` class that:
  - Takes a path to `context_runtime.yaml` in its constructor
  - Has a `read()` method that returns the parsed YAML as a dict
  - Has a `write(data: dict)` method that serializes the dict back to YAML
  - Wraps both methods with a file lock so concurrent access is safe
- `[ ]` Write tests for: normal read, normal write, reading a file that does not exist (should raise a clear error, not a confusing Python exception), writing preserves all existing keys
- `[ ]` **Challenge yourself:** What happens if the program crashes mid-write? Look up "atomic file write" (write to a temp file, then rename) and implement it — this is the basis of the atomicity requirement in the architecture docs

### 2.3 — BaseController

> 📖 *What to study first:* Python dataclasses (`@dataclass` decorator) — a clean way to define classes that are mainly data containers. Also read about `typing` module (`Optional`, `Dict`, `List`) — typed code is much easier to debug.

- `[ ]` Create `pdsno/controllers/base_controller.py` with a `BaseController` class that has:
  - `controller_id: str` — the controller's unique identifier
  - `role: str` — `"global"`, `"regional"`, or `"local"`
  - `context_manager: ContextManager` — injected in the constructor, not created internally
  - `logger` — obtained via `get_logger(controller_id)` in `__init__`
  - A `load_algorithm(algorithm_class)` method that instantiates the algorithm
  - A `run_algorithm(algorithm_instance, context: dict)` method that runs the full `initialize → execute → finalize` lifecycle, logs each phase, and returns the result payload
- `[ ]` Write tests for: loading and running a `DummyAlgorithm` through a `BaseController`, logging is called at each phase (use `unittest.mock` to capture log calls)

---

## Phase 3 — NIB (Network Information Base, Minimal Version)

> **Goal:** A working SQLite-backed NIB with the core tables from the NIB spec, a clean Python interface, and optimistic locking for conflict detection. This is the most technically involved phase so far — take your time.
>
> **What "done" looks like:** You can insert a device record, update it, simulate a write conflict, and see the conflict detected and handled correctly. All through the `NIBStore` interface with no direct SQL anywhere else.
>
> **Entry Requirement:** Phase 2 complete.

### 3.1 — SQLite Basics

> 📖 *What to study first:* SQLite in Python — the built-in `sqlite3` module. Specifically: `connect()`, `cursor()`, `execute()`, `fetchone()`, `fetchall()`, `commit()`. Also understand what a transaction is and why `commit()` is needed. This is a 2–3 hour study session before writing any code.

- `[ ]` Create `pdsno/data/nib_store.py` — start with just the database initialization
- `[ ]` On first run, it creates a SQLite file at a configurable path (`pdsno.db` by default in the `config/` folder)
- `[ ]` Implement `_initialize_schema()` — creates all six tables from the NIB spec if they don't already exist
- `[ ]` Add a `version INTEGER NOT NULL DEFAULT 0` column to every mutable table (Device, Config, Policy, Controller Sync) — this is what optimistic locking uses
- `[ ]` Write a test that creates a `NIBStore`, calls `_initialize_schema()` twice (idempotent — it should not fail the second time), and confirms the tables exist

### 3.2 — Device Table Operations

> 📖 *What to study first:* Python dataclasses for the `Device` model. Also `Optional` from `typing` — some fields in the device table can be null.

- `[ ]` Create `pdsno/data/models.py` — a `Device` dataclass with all fields from the NIB spec schema
- `[ ]` Implement `NIBStore.get_device(device_id: str) -> Device | None`
- `[ ]` Implement `NIBStore.get_device_by_mac(mac: str) -> Device | None`
- `[ ]` Implement `NIBStore.upsert_device(device: Device) -> NIBResult`
  - If the device doesn't exist: insert it with `version=0`
  - If it exists: check that the caller's `device.version` matches the stored version. If it matches, update and increment version. If it doesn't match, return `NIBResult(success=False, error="CONFLICT")`
- `[ ]` Write tests covering: insert new device, update existing device, detect write conflict (two "threads" read version 0, first write succeeds, second write returns CONFLICT)

### 3.3 — Event Log

> 📖 *What to study first:* Python's `datetime` module and `timezone.utc` — always store timestamps in UTC, never local time. Also HMAC from Python's `hmac` module — we use this to sign event log entries so they are tamper-evident.

- `[ ]` Create `Event` dataclass in `models.py`
- `[ ]` Implement `NIBStore.write_event(event: Event) -> NIBResult`
- `[ ]` Sign each event before writing: `signature = hmac.new(secret_key, event_content_bytes, hashlib.sha256).hexdigest()`
- `[ ]` Add a database trigger that raises an error if any UPDATE or DELETE is attempted on the Event Log table — this enforces append-only at the database level
- `[ ]` Write tests: write event, confirm it exists, confirm the trigger prevents deletion

### 3.4 — Controller Sync Table (Locks)

> 📖 *What to study first:* What a database transaction is, and Python's context manager (`with` statement) — SQLite supports `with connection` as a transaction scope.

- `[ ]` Implement `NIBStore.acquire_lock(subject_id, lock_type, held_by, ttl_seconds) -> NIBResult`
  - Fails if an unexpired lock already exists for this `subject_id` + `lock_type`
  - Succeeds otherwise, creating a lock record with an expiry timestamp
- `[ ]` Implement `NIBStore.release_lock(lock_id, held_by) -> NIBResult`
  - Only the controller that acquired the lock can release it
- `[ ]` Implement `NIBStore.check_lock(subject_id, lock_type) -> Lock | None`
  - Returns the active lock if one exists, `None` if not or if the lock has expired
- `[ ]` Write tests for: acquire lock, fail to acquire when locked, release lock, acquire after release, expired lock is treated as not held

---

## Phase 4 — Controller Validation (First Real Feature)

> **Goal:** A runnable simulation where a `RegionalController` sends a validation request to a `GlobalController`, the full challenge-response flow runs, and the Regional Controller receives a certificate and has its identity written to the NIB. This is the first moment PDSNO does something real.
>
> **What "done" looks like:** You run `python simulate_validation.py` and see log output showing each step of the validation flow, ending with "regional_cntl_1 validated and assigned identity."
>
> **Entry Requirement:** Phase 3 complete, `docs/api_reference.md` complete (message formats must be decided before implementing them).

### 4.1 — Message Types

> 📖 *What to study first:* Python dataclasses with `field(default_factory=...)` for complex defaults. Also `uuid` module — `uuid.uuid4()` generates unique IDs.

- `[ ]` Create `pdsno/communication/messages.py`
- `[ ]` Define dataclasses for each message type: `RegistrationRequest`, `ChallengeMessage`, `ChallengeResponse`, `ValidationResponse`
- `[ ]` Every message must have: `message_id` (UUID), `timestamp` (UTC datetime), `sender_id` (controller ID)
- `[ ]` Write a test that creates each message type and confirms required fields are present

### 4.2 — In-Process Message Bus

> 📖 *What to study first:* Python functions as first-class objects — you can pass a function as an argument to another function. This is how the simple message bus works: controllers register a handler function, and the bus calls it when a message arrives.

- `[ ]` Create `pdsno/communication/message_bus.py` — a `MessageBus` class that:
  - Has a `register(controller_id: str, handler: callable)` method
  - Has a `send(sender_id: str, recipient_id: str, message)` method that calls the recipient's handler synchronously
  - Logs every send with sender, recipient, and message type
- `[ ]` This is intentionally simple — no queues, no async, no network. Just function calls. Complexity comes in Phase 5.
- `[ ]` Write tests: register two controllers, send a message, confirm the handler was called with the right message

### 4.3 — Validation Logic

> 📖 *What to study first:* Python's `hmac` module for HMAC-SHA256. Also `hashlib`. Also Python's `datetime` arithmetic — `datetime.now(utc) - request.timestamp` gives you a `timedelta` you can check against a freshness window.

- `[ ]` Create `pdsno/controllers/global_controller.py` — inherits `BaseController`
- `[ ]` Implement `handle_registration_request(request: RegistrationRequest)` — this is the main validation method, following the pseudocode in `controller_validation_sequence.md` step by step:
  - Step 1: Check timestamp freshness (reject if older than `FRESHNESS_WINDOW_MINUTES`, default 5)
  - Step 2: Check blocklist (load from `context_runtime.yaml`, reject if `temp_id` is in the list)
  - Step 3: Verify bootstrap token (HMAC — shared secret loaded from config)
  - Step 4: Generate nonce, send challenge via `MessageBus`, wait for signed response
  - Step 5: Verify the signature on the challenge response
  - Step 6: Assign identity, write to NIB and context atomically
- `[ ]` Create `pdsno/controllers/regional_controller.py` — inherits `BaseController`, implements `request_validation(global_controller_id)` that builds and sends a `RegistrationRequest`
- `[ ]` Write tests for every rejection path before testing the happy path — this is good engineering practice

### 4.4 — Simulation Script

- `[ ]` Create `simulate_validation.py` in the project root
- `[ ]` Script sets up: one `GlobalController`, one `RegionalController`, one `MessageBus`, one `NIBStore`, one `ContextManager`
- `[ ]` Regional Controller calls `request_validation()`, the full flow runs, the script prints the outcome
- `[ ]` Run it. Fix what breaks. This is where the architecture meets reality for the first time.

---

## Phase 5 — Discovery Module

> **Goal:** A working `ARPScan` algorithm that runs inside a `LocalController`, produces a device list, reports it to the `RegionalController`, and stores results in the NIB.
>
> **What "done" looks like:** You run `simulate_discovery.py` and see a Local Controller scan a subnet, report discovered devices to the Regional Controller, and those devices appear in the NIB.
>
> **Entry Requirement:** Phase 4 complete, network access available for ARP scanning.

- `[ ]` Implement `ARPScan` algorithm inheriting `AlgorithmBase`
  - 📖 *Study first:* Python's `scapy` library for ARP — add it to `requirements.txt`
  - `initialize()` takes `{"subnet": "192.168.1.0/24"}` in context
  - `execute()` runs the ARP scan and returns a list of `{"ip": ..., "mac": ...}` dicts
  - `finalize()` returns the standard result payload
- `[ ]` Implement `ICMPPing` algorithm — simpler than ARP, uses `ping3` library
- `[ ]` Implement `LocalController` — inherits `BaseController`, orchestrates running both scan algorithms in sequence (parallel execution comes in Phase 6)
- `[ ]` Implement discovery report formatting: converts raw scan results into the NIB `Device` format
- `[ ]` Implement `RegionalController.handle_discovery_report()` — validates the report and writes devices to the NIB
- `[ ]` Write `simulate_discovery.py` end-to-end simulation script

---

## Phase 6 — Real Communication Layer

> **Goal:** Replace the in-process message bus with real HTTP communication using FastAPI. Controllers run as separate processes and talk to each other over localhost, then over a real network.
>
> **Entry Requirement:** Phase 5 complete.
>
> 📖 *Study first:* FastAPI basics (routing, Pydantic models, `uvicorn`), Python's `requests` library, and what a REST API actually is if not already comfortable with it.

- `[ ]` Add `fastapi`, `uvicorn`, `requests`, and `pydantic` to `requirements.txt`
- `[ ]` Create a REST endpoint for each message type in `GlobalController` and `RegionalController`
- `[ ]` Replace `MessageBus` calls with HTTP POST requests
- `[ ]` Add request signing to every outbound HTTP call (HMAC of the request body, sent as a header)
- `[ ]` Add signature verification to every inbound endpoint
- `[ ]` Run GC and RC as separate processes on the same machine and repeat the validation simulation
- `[ ]` Run GC on one machine, RC on another, and repeat — this is the first real distributed test

---

## Phase 7 — Configuration Approval Logic

> **Goal:** Implement the full config approval flow with sensitivity tiers, execution tokens, and audit logging.
>
> **Entry Requirement:** Phase 6 complete, `docs/architecture/approval_logic/config_approval_doc.md` finalized.

- `[ ]` Implement config proposal creation in `LocalController`
- `[ ]` Implement sensitivity classification in `RegionalController`
- `[ ]` Implement execution token issuance (signed JWT — add `python-jose` to requirements)
  - 📖 *Study first:* What a JWT is and how signing/verification works
- `[ ]` Implement token verification in `LocalController` before executing any config
- `[ ]` Implement escalation path to `GlobalController` for HIGH sensitivity
- `[ ]` Implement emergency fast path with rate limiting
- `[ ]` Implement rollback instruction storage and execution
- `[ ]` Write end-to-end tests for all four sensitivity categories (LOW, MEDIUM, HIGH, EMERGENCY)

---

## Phase 8 — Hardening & Developer Experience

> **Goal:** Make the PoC presentable, reliable, and approachable for external contributors.

- `[ ]` Add structured telemetry: track validation success/failure rates, approval decision counts, scan durations
- `[ ]` Write a sandbox mode: single script that spins up all three controller tiers in separate threads, runs a full scenario (validation → discovery → config approval), and exits cleanly
- `[ ]` Review all audit log entries against the threat model — confirm every threat scenario from T1–T9 produces the correct audit trail
- `[ ]` Complete `docs/deployment_guide.md` based on the actual experience of setting up the PoC
- `[ ]` Write `CONTRIBUTING.md` — setup instructions based on real experience, not speculation
- `[ ]` Create GitHub Actions CI: on every PR, run `pytest` and confirm all tests pass

---

## Parking Lot — Future Phases (Not Scheduled Yet)

These are real goals from the roadmap that are explicitly deferred. They are noted here so they do not get lost, but they should not influence Phase 0–3 design decisions unless unavoidable.

- AI/ML decision layer for predictive congestion and anomaly detection
- Kubernetes/Docker orchestration support
- Distributed validation ledger (blockchain-inspired audit)
- Multi-tenant and multi-domain support
- gRPC endpoints alongside REST
- Dynamic role promotion/demotion for controllers
- Risk scoring engine fed by NIB device history
- Multi-signature approvals for critical changes

---

## Key Architectural Decisions Log

> Record decisions here as they are made. Each entry should state what was decided, why, and what alternatives were rejected.

| # | Decision | Rationale | Date | Alternatives Rejected |
|---|----------|-----------|------|----------------------|
| 1 | SQLite for NIB in PoC | Lightweight, zero-config, good enough for single-machine testing. Swappable via `NIBStore` interface later. | Feb 2026 | Redis (overkill for PoC), flat files (no query capability) |
| 2 | HMAC for PoC auth, real PKI in Phase 6 | Allows all validation logic to be written and tested without full PKI infrastructure. HMAC is cryptographically sound for the PoC. | Feb 2026 | Full X.509 PKI from day one (too much setup complexity before core logic is validated) |
| 3 | Python for all PoC phases | Fastest iteration, extensive networking libraries, lowest barrier for learning | Feb 2026 | Go (better for production concurrency but slower to prototype and learn simultaneously) |
| 4 | In-process message bus for Phases 1–5 | Eliminates all network complexity while core logic is being built and tested | Feb 2026 | REST from day one (introduces infrastructure complexity before the logic works) |
| 5 | Per-subject optimistic locking for NIB (PoC), adaptive consistency as Phase 6+ target | Optimistic locking catches dangerous conflicts without Raft complexity. Adaptive consistency (strong for critical ops, eventual for transient) is research-recommended for production distributed SDN. | Feb 2026 | Static eventual consistency (too risky), static strong consistency (too complex for PoC) |
| 6 | Signed JSON object as PoC "certificate" | Simple to implement, serializable, verifiable with HMAC. Ed25519 asymmetric signatures in Phase 6. | Feb 2026 | JWT (unnecessary dependency), YAML struct (not cryptographically signable) |
| 7 | REST for request/response, MQTT for events/broadcasts | Research-validated split (Alsheikh et al. 2024). REST maps to synchronous flows with definite outcomes. MQTT pub/sub eliminates polling overhead for state updates and policy distribution. | Feb 2026 | REST for everything (polling overhead), MQTT for everything (poor fit for request/response) |
| 8 | Delta-sync for inter-controller state exchange | Full state dumps don't scale. Only changed entities (with version numbers) are exchanged. Adopted from DISCO architecture (Phemius et al. 2014). | Feb 2026 | Periodic full state exchange (bandwidth and CPU intensive at scale) |
| 9 | Two-tier NIB storage target (transient + durable) | Onix production architecture uses DHT for transient data and Paxos-backed storage for durable data. PDSNO targets Redis + PostgreSQL/etcd for the same split. Single SQLite tier for PoC. | Feb 2026 | Single consistent store for everything (performance bottleneck at scale) |

---

## Questions & Open Issues

> Things that need a decision before the relevant phase begins. Do not start implementation until these are resolved.

- **~~Q1 (Blocking Phase 0.3):~~** ✅ *Resolved* — NIB uses per-subject optimistic locking with adaptive consistency as the Phase 6+ target. Rationale documented in `nib_spec.md`. Research basis: Alsheikh et al. (ARO 2024), Koponen et al. (Onix, OSDI 2010).

- **~~Q2 (Blocking Phase 1.4):~~** ✅ *Resolved* — PoC uses a signed JSON object (HMAC-SHA256, serialized to a dict with `assigned_id`, `role`, `expiry`, `issuer_id`, `signature`). Full asymmetric cryptography (Ed25519) in Phase 6.

- **~~Q3 (Blocking Phase 6):~~** ✅ *Resolved* — REST for request/response flows (validation, config approval, discovery reports). MQTT pub/sub for broadcast/event flows (policy distribution, state change notifications, NIB sync). Research basis: Alsheikh et al. (ARO 2024) recommends pub/sub over polling for state updates. Documented in `communication_model.md`.

- **Q4 (Design — Non-blocking for now):** The current design has a single `global_cntl_1` as root of trust. What happens when it is offline? Is there a failover mechanism, and if so, how does `global_cntl_2` inherit the trust anchor role safely? *Must be resolved before Phase 6 (real network deployment).*

---

*This document is a living artifact. Update task statuses as work progresses and add new questions to the Open Issues section as they arise.*
