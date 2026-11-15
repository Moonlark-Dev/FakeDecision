# Security & responsible use

FakeDecision is a **private-use** application that simulates provider APIs with human answers. It must not be operated as a public or commercial service, and must not be used to misrepresent a real provider, deceive people, bypass controls or commit fraud.

## Deployment expectations

- Bind to localhost or a private network by default.
- If exposing through a reverse proxy, use TLS, strong admin credentials, and a restrictive network policy.
- Set `FAKE_DECISION_PUBLIC_URL` and only enable `FAKE_DECISION_TRUST_PROXY` behind a trusted proxy.
- Keep `data/` (SQLite plus generated secret) out of version control and backups of unknown provenance.
- This project has no billing/payment code and no way to enable charging.

## Reporting

This is a private-use project. If you find a vulnerability, open a private security advisory in the repository or contact the maintainers; do not publish exploit details before a fix is available. No warranty is provided.
