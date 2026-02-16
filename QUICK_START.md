# PDSNO Quick Start Guide

## Installation

1. **Clone the repository** (if not already done)

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify installation:**
   ```bash
   python PDSNO/main.py
   ```

   You should see the PDSNO banner with implemented components listed.

---

## Quick Examples

### 1. Run the Main Entry Point

```bash
python PDSNO/main.py
```

This shows the current implementation status and available components.

### 2. Try the Algorithm Example

```bash
python examples/basic_algorithm_usage.py
```

This demonstrates:
- Creating a custom algorithm
- Running it through a controller
- The three-phase lifecycle (initialize → execute → finalize)

### 3. Try the NIB Example

```bash
python examples/nib_store_usage.py
```

This demonstrates:
- Storing network device information
- Optimistic locking for concurrent access
- Event logging for audit trails
- Lock coordination between controllers

### 4. Run the Tests

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run specific test file
python -m pytest tests/test_base_classes.py

# Run with coverage
python -m pytest --cov=PDSNO
```

---

## Basic Usage Patterns

### Creating a Custom Algorithm

```python
from PDSNO.core.base_class import AlgorithmBase
from datetime import datetime, timezone

class MyAlgorithm(AlgorithmBase):
    def initialize(self, context):
        # Load inputs from context
        self.input_data = context.get('data', [])
        self._initialized = True
    
    def execute(self):
        super().execute()  # Validates initialization
        # Your logic here
        self.result = sum(self.input_data)
        self._executed = True
        return self.result
    
    def finalize(self):
        super().finalize()  # Validates execution
        return {
            "status": "complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": self.result
        }
```

### Running an Algorithm

```python
from PDSNO.controllers import BaseController, ContextManager

# Setup
context_mgr = ContextManager("config/context_runtime.yaml")
controller = BaseController(
    controller_id="my_controller",
    role="local",
    context_manager=context_mgr
)

# Run algorithm
algorithm = MyAlgorithm()
result = controller.run_algorithm(algorithm, {'data': [1, 2, 3, 4, 5]})
print(f"Result: {result['result']}")  # Output: 15
```

### Working with the NIB

```python
from PDSNO.datastore import NIBStore, Device, DeviceStatus

# Initialize NIB
nib = NIBStore("config/pdsno.db")

# Create device
device = Device(
    device_id="",
    ip_address="192.168.1.100",
    mac_address="AA:BB:CC:DD:EE:FF",
    hostname="switch-1",
    status=DeviceStatus.DISCOVERED
)

# Store device
result = nib.upsert_device(device)
if result.success:
    print(f"Device stored with ID: {result.data}")

# Retrieve device
retrieved = nib.get_device_by_mac("AA:BB:CC:DD:EE:FF")
print(f"Device: {retrieved.hostname}")
```

---

## Project Structure

```
PDSNO/
├── core/                  # Base classes (AlgorithmBase)
├── controllers/           # BaseController, ContextManager
├── datastore/            # NIBStore, data models
├── communication/        # Message formats, REST API
├── logging/              # Structured JSON logging
├── utils/               # Config loader, helpers
└── main.py              # Entry point

tests/                    # Test suite
├── conftest.py          # Pytest fixtures
├── test_base_classes.py # Algorithm & controller tests
└── test_datastore.py    # NIB tests

examples/                 # Working examples
├── basic_algorithm_usage.py
├── nib_store_usage.py
└── README.md

docs/                     # Comprehensive documentation
├── INDEX.md             # Start here
├── ROADMAP_AND_TODO.md  # Development plan
├── algorithm_lifecycle.md
├── nib_spec.md
└── ... (many more)
```

---

## Key Concepts

### 1. Algorithm Lifecycle

Every algorithm follows three phases:
1. **Initialize** - Load configuration and prepare
2. **Execute** - Run the logic
3. **Finalize** - Clean up and return results

The controller enforces this order automatically.

### 2. Network Information Base (NIB)

The NIB is the authoritative source of truth for all network state:
- Device information
- Configuration history
- Policy distribution
- Event log (audit trail)
- Coordination locks

Controllers read from and write to the NIB, never storing their own state.

### 3. Optimistic Locking

The NIB uses version-based optimistic locking to detect write conflicts:
- Each record has a `version` field
- Updates only succeed if the version matches
- Prevents two controllers from overwriting each other's changes

### 4. Structured Logging

All logs are JSON-formatted for machine parsing:
```json
{
  "timestamp": "2026-02-16T10:30:00Z",
  "level": "INFO", 
  "controller_id": "local_cntl_1",
  "message": "Device discovered",
  "module": "discovery"
}
```

---

## Common Tasks

### Add a New Algorithm

1. Create file in `PDSNO/algorithms/` (create directory if needed)
2. Inherit from `AlgorithmBase`
3. Implement `initialize()`, `execute()`, `finalize()`
4. Write tests in `tests/test_algorithms.py`

### Add a New NIB Table

1. Update `PDSNO/datastore/models.py` with new dataclass
2. Update `NIBStore._initialize_schema()` with SQL
3. Add methods to `NIBStore` for CRUD operations
4. Write tests in `tests/test_datastore.py`

### Add a New Message Type

1. Add enum value to `MessageType` in `message_format.py`
2. Create message dataclass with `to_dict()` method
3. Update `docs/api_reference.md` with specification
4. Write tests in `tests/test_communication.py`

---

## Documentation

### Essential Reading

1. **[UPDATE_SUMMARY.md](UPDATE_SUMMARY.md)** - What changed in this update
2. **[docs/INDEX.md](docs/INDEX.md)** - Documentation navigation
3. **[docs/ROADMAP_AND_TODO.md](docs/ROADMAP_AND_TODO.md)** - Development plan
4. **[docs/algorithm_lifecycle.md](docs/algorithm_lifecycle.md)** - Algorithm pattern
5. **[docs/nib_spec.md](docs/nib_spec.md)** - NIB specification

### For Learning

- Start with `examples/` - working code you can run and modify
- Read `docs/PROJECT_OVERVIEW.md` - architectural foundations
- Review `docs/architecture.md` - system design
- Check `docs/ROADMAP_AND_TODO.md` - what's next

---

## Troubleshooting

### Import Errors

Make sure you're in the project root directory:
```bash
cd /path/to/Partially-Distributed-Smart-Network-Optimizer-PDSNO-
python examples/basic_algorithm_usage.py
```

### Test Failures

```bash
# Clean build artifacts
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null

# Reinstall dependencies
pip install -r requirements.txt --upgrade

# Run tests
python -m pytest -v
```

### Database Issues

Delete and recreate:
```bash
rm config/pdsno.db
python examples/nib_store_usage.py
```

---

## Next Steps

1. ✅ **Run examples** to see the system in action
2. ✅ **Run tests** to validate your environment
3. ✅ **Read documentation** starting with INDEX.md
4. ✅ **Review ROADMAP** to understand development phases
5. 🔲 **Implement Phase 4** (Controller validation) - See ROADMAP

---

## Getting Help

- Check [UPDATE_SUMMARY.md](UPDATE_SUMMARY.md) for recent changes
- Review [docs/ROADMAP_AND_TODO.md](docs/ROADMAP_AND_TODO.md) for context
- See [examples/](examples/) for working code patterns
- Check test files for usage examples

---

**Happy coding! 🚀**
