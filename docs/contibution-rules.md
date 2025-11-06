# 🧱 Architecture Review Rules

To keep PDSNO consistent and scalable as contributors join, all new modules and features must align with the **core orchestration model** and **system architecture principles**.

---

## 1. Orchestration Alignment

- All components must fit into one of the controller tiers:
  - **Global Controller** — policy and coordination
  - **Regional Controller** — zone-level optimization
  - **Local Controller** — device-level interaction
- New modules must clearly state their **tier** and **communication interface**.

---

## 2. Communication Model

- Inter-controller communication should use **REST** or **MQTT**, depending on latency and state requirements.
- No module should directly access another tier’s internal data structures.
- Use YAML or JSON for configuration and message schemas.

---

## 3. Data Flow and Logging

- All data interactions must be **logged** and **traceable**.
- Dynamic updates should follow the **event-driven pattern** (publish/subscribe).
- Avoid redundant update loops — refer to `docs/architecture-overview.md` for flow examples.

---

## 4. Technology Alignment

- **Initial implementation:** Python (proof of concept)
- **Performance modules:** Go or Rust (future optimization)
- **Web/API layer:** Node.js or FastAPI

Each proposal must specify which language is used and why.

---

## 5. Review Process

Every PR introducing new logic or module must:
1. Reference an approved issue
2. Include a short **architecture alignment section** in the PR description
3. Pass code review by at least **one core maintainer**

---

## 6. Documentation Requirement

Each accepted contribution must include:
- README or docstring explaining purpose
- Example YAML configuration if applicable
- Update to `/docs/architecture-overview.md` if it affects system flow
