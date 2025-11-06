# Contributing to PDSNO

Welcome to **PDSNO (Partially Distributed Smart Network Orchestrator)** — an open-source project designed to build the foundation of next-generation intelligent network orchestration.

We’re glad you’re here! This guide explains **how to propose ideas, submit changes, and stay aligned with the system’s architecture**.

---

## 1. Before You Start

- Read the [Project Overview](./README.md) and [Roadmap](../docs/roadmap.md)
- Review the [Architecture Overview](../docs/architecture-overview.md)
- Join or open a **GitHub Discussion** to share your ideas before writing code

---

## 2. How to Propose a Change

All changes — including new modules, API updates, or configuration designs — must go through a transparent discussion process.

1. **Open a GitHub Issue**:
   - Choose an appropriate tag (`proposal`, `bug`, `enhancement`)
   - Describe the motivation, expected behavior, and system impact
   - Attach diagrams, mockups, or YAML examples if relevant

2. **Participate in Discussion**:
   - Feedback will happen under **GitHub Discussions**
   - Once consensus is reached, maintainers will assign the issue to you

3. **Create a Pull Request (PR)**:
   - Reference the issue (`Closes #<issue_number>`)
   - Follow the [Architecture Rules](../docs/contribution-rules.md)
   - Request a **review from the architecture or core team**

---

## 3. Coding Guidelines

- **Language**: Python (initial PoC); later, polyglot modules (Go, Rust, Node.js)
- **Formatting**: Follow PEP8 and Black formatter
- **Docs**: Every module must include a docstring explaining purpose and data flow
- **Testing**: Unit tests required for all major functions or services

---

## 4. Architecture Alignment

Every new module or function **must align** with the PDSNO orchestration hierarchy and communication model.

See [Architecture Review Rules](../docs/contribution-rules.md) for details.

---

## 5. Communication Channels

-  **Discussions** → For ideas, architecture debates, and design questions  
-  **Issues** → For bugs, improvements, and implementation tasks  
-  **Pull Requests** → For completed contributions awaiting review  

---

## 6. Recognition

All merged contributors are listed in the [Contributors](https://github.com/<your-repo>/graphs/contributors) section.  
Consistent contributors may be invited as **maintainers** for specific modules.

---

Thank you for helping make PDSNO better, smarter, and more open..
