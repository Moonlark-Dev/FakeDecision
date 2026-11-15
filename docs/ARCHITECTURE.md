# Architecture

```text
Client ──HTTP──> /v1/systemone or /v1beta/decisions
                    │
                    ▼
             protocol parser / validator
                    │
                    ▼
              SQLite request row
                    │
       ┌────────────┴─────────────┐
       │                          │
  RealtimeHub                RequestService
  (operator sockets)          deadline monitor
       │                          │
       ▼                          │
  /admin queue                    │
  human editor                    │
       │                          │
       └──────────answer──────────┘
                    │
                    ▼
          response codec (exact
          provider-shaped JSON)
```

## Components

- **`RequestService`** owns the request state machine: `queued → assigned → answered|timed_out|cancelled`. It selects the least-busy online operator assigned to the model, stores drafts, and arms two timers:
  - `auto_fill_at` when auto-fill is enabled, before the hard deadline;
  - `deadline_at` otherwise.
- **`RealtimeHub`** is an in-process fan-out with one bounded queue per browser tab. Slow tabs drop events; the REST snapshot is authoritative.
- **Protocol codecs** validate and normalize both wire formats into a canonical `ParsedRequest`, and convert canonical answers back into the exact provider envelope. Probabilities are normalized, rounded and repaired only for rounding-scale drift.
- **SQLite** uses WAL mode, foreign keys, busy timeout and short-lived connections. The schema is initialized idempotently at startup.
- **SPA hosting** is served by FastAPI from `fake_decision/web/dist`; unknown non-API paths return `index.html`.

## State & data

- `requests` stores immutable input/questions plus status, draft, final answers, timings and assignment.
- `users`, `backoffice_users`, `sessions`, `api_keys`, `models`, `model_assignments`, `settings`, `audit_logs`.
- Session tokens and API keys are stored only as hashes.
- On restart, any interrupted `queued`/`assigned` requests are marked `timed_out` with `server_restart` so no HTTP client waits forever.

## Threat model

The app is intended for a trusted private network. It still implements defense in depth: hashed credentials, scoped operator access, CSRF-origin checks, CSP/XFO/noindex, rate limits, request size limits, and hashed API keys. It does not attempt to defend against a hostile host administrator or a compromised browser.
