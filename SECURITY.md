# Security Policy

Thank you for helping keep **PDSNO (Partially Distributed Smart Network Orchestrator)** and its users secure.

---

## Supported Versions

Security updates are applied to the **main** development branch and any active release branches.

| Version | Supported |
|----------|------------|
| main (development) | Active |
| pre-release / beta | Limited |
| older branches | Not supported |

---

## Reporting a Vulnerability

If you discover a security vulnerability, please **DO NOT** open a public GitHub issue.

Instead, report it confidentially via:

**security@atlasiris.org**  
or use GitHub private vulnerability reporting (when enabled for this repository).

Please include:

- A clear description of the issue  
- Steps to reproduce (if possible)  
- Suggested mitigations or fixes (optional)

We will:

1. Acknowledge your report within **3–5 business days**  
2. Investigate and confirm the issue  
3. Work on a fix and coordinate responsible disclosure  
4. Credit you (if desired) once the issue is resolved

---

## Security Practices

PDSNO is designed with **distributed control, isolation, and data minimization** in mind.  
To maintain security integrity:

- Sensitive network data is not stored — only metadata for analysis  
- Communication between controllers will adopt encrypted channels (TLS/MQTT over SSL)  
- Role-based access control (RBAC) will be implemented for orchestration tasks  
- Contributions introducing external dependencies will undergo review

---

## Long-Term Vision

As the project matures, we plan to integrate:

- Automated dependency scanning (Dependabot)  
- CodeQL analysis for Python and future language modules  
- Security testing pipelines during CI/CD  
- Documentation of secure plugin development practices

---

## Responsible Disclosure

We encourage ethical research and responsible reporting.  
Please give us time to patch before publicly disclosing vulnerabilities.

---

Thank you for helping us make **PDSNO** a safer, more resilient open platform.
