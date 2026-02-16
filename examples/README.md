# PDSNO Examples

This directory contains example scripts demonstrating how to use PDSNO components.

## Available Examples

### 1. basic_algorithm_usage.py
Demonstrates the algorithm lifecycle pattern (initialize → execute → finalize).

**Shows:**
- Creating a custom algorithm that inherits from `AlgorithmBase`
- Using `BaseController` to run algorithms
- Context management and configuration
- Structured logging output

**Run:**
```bash
python examples/basic_algorithm_usage.py
```

### 2. nib_store_usage.py
Demonstrates NIB (Network Information Base) operations.

**Shows:**
- Creating and storing device records
- Retrieving devices by MAC address
- Optimistic locking for concurrent writes
- Event log (audit trail) usage
- Lock acquisition and release for coordination

**Run:**
```bash
python examples/nib_store_usage.py
```

## Requirements

Make sure you have installed the dependencies:

```bash
pip install -r requirements.txt
```

## Understanding the Examples

These examples correspond to Phase 1-3 of the development roadmap in `docs/ROADMAP_AND_TODO.md`:

- **Phase 1**: Project foundation, logging, folder structure
- **Phase 2**: Base classes (AlgorithmBase, BaseController, ContextManager)
- **Phase 3**: NIB implementation with SQLite

The examples are designed to be educational and demonstrate the architectural patterns documented in:
- `docs/algorithm_lifecycle.md` - Algorithm pattern
- `docs/nib_spec.md` - NIB specification
- `docs/PROJECT_OVERVIEW.md` - Overall architecture

## Next Steps

After exploring these examples, you can:

1. **Run the tests**: `python -m pytest`
2. **Review the documentation**: Start with `docs/INDEX.md`
3. **Continue development**: See `docs/ROADMAP_AND_TODO.md` for Phase 4+
