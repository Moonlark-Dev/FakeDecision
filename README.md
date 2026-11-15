# FakeDecision

> **Human-in-the-loop System One / Gemini Decisions compatible API provider.**
>
> A private deployment that looks and behaves like a decision-model provider from the outside, while a human operator answers every request in a dedicated operations console.

[![CI](https://github.com/Moonlark-Dev/FakeDecision/actions/workflows/ci.yml/badge.svg)](https://github.com/Moonlark-Dev/FakeDecision/actions/workflows/ci.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)

---

## ⚠️ Legal warning — read before deploying

<a name="legal-warning"></a>

**FakeDecision is for private, local and research use only.**

It deliberately imitates decision-model provider APIs while answers are produced by humans. **Do not deploy it as a public or commercial service, do not advertise it as a real model provider, and do not use it to deceive users, bypass access controls, or commit fraud.** Public deployment, misrepresentation, impersonation and commercial use may violate applicable law, platform terms and the rights of third parties. You are solely responsible for your deployment.

The server prints a bilingual warning at startup and this repository does not implement any billing, payment, credit or metering functionality. There is intentionally **no way to enable charging** in the product.

License: **GNU AGPL-3.0-or-later**. No warranty.

---

## What it is

FakeDecision is a full-stack application:

- **FastAPI + SQLite** backend.
- **Vue 3 + TypeScript + Vite** frontend.
- **Public provider site**: home, model catalog, docs, registration, login, console with an OpenRouter-style try-out.
- **Internal operations console** at `/admin`: live decision queue over WebSocket, human answer editor, model-to-operator routing, users, models, settings, audit log and data export.
- **Two provider APIs implemented end to end**:
  - System One / TypeSafe-compatible `POST /v1/systemone`.
  - Google Gemini Decisions-compatible `POST /v1beta/decisions`.
- **Human answer engine**: per-question random fill with realistic calibrated distributions, whole-request random fill, draft autosave, hard deadlines and automatic random completion shortly before timeout.
- **Nuitka standalone executables** for Linux and Windows x86_64, built and verified by CI; tagged releases attach both to GitHub Releases.
- `robots.txt` disallows all crawlers; every response carries `X-Robots-Tag: noindex`.

The public site never links to, names, or hints at the admin console. The admin console has its own login at `/admin/login`.

## Screens

| Public | Console | Admin |
| --- | --- | --- |
| Provider landing with typed-decision examples | OpenRouter-style playground + API keys | Live human decision queue |
| Model catalog and docs | Usage and account | Operator/model routing |
| Register / sign in | Quickstart snippets | Users, settings, audit, export |

## Quick start (local)

Requirements: Python 3.11+, Node 22+, pnpm 9+.

```bash
git clone https://github.com/Moonlark-Dev/FakeDecision.git
cd FakeDecision

# Frontend
cd frontend
pnpm install --frozen-lockfile
pnpm build
cd ..

# Backend (system Python, or use a venv)
pip install -r backend/requirements-dev.txt
export PYTHONPATH="$PWD/backend"
export FAKE_DECISION_DATA_DIR="$PWD/data"
export FAKE_DECISION_ADMIN_EMAIL="admin@fakedecision.local"
# Optional; if omitted a strong password is generated and printed once.
export FAKE_DECISION_ADMIN_PASSWORD="change-this-password"

python -m fake_decision --host 0.0.0.0 --port 8790
```

Open:

- Public site: `http://localhost:8790/`
- Admin console: `http://localhost:8790/admin`
- Health: `http://localhost:8790/healthz`

On first start the server initializes SQLite, creates the admin account and prints the credentials (generated credentials are shown **only once**). The startup banner also prints the legal warning.

### One-command preview

```bash
bash scripts/preview.sh
```

This builds the frontend and starts the server on `0.0.0.0:8790` (override with `FAKE_DECISION_PORT` / extra CLI flags). Useful for testing on a LAN address such as `http://192.168.1.20:8790`.

## Deploy from a release

Prebuilt standalone executables for Linux x86_64 and Windows x86_64 are attached to every tagged [GitHub Release](https://github.com/Moonlark-Dev/FakeDecision/releases). They bundle Python, the backend and the built frontend, so the target machine needs no Python, Node or pnpm toolchain. Use this path for a real installation; the quick-start above is for development.

Replace `vX.Y.Z` with the release tag you are installing.

| Release asset | Platform | Unpacks to |
| --- | --- | --- |
| `FakeDecision-linux-x86_64.tar.gz` + `.sha256` | Linux x86_64 | `FakeDecision-linux-x86_64/` with `fakedecision`, `README.md`, `LICENSE`, `RUN.txt`, `data/` |
| `FakeDecision-windows-x86_64.zip` + `.sha256` | Windows x86_64 | `FakeDecision-windows-x86_64/` with `fakedecision.exe`, `README.md`, `LICENSE`, `RUN.txt`, `data/` |

The executables target x86_64 CPUs only. They are not code-signed on Windows, so SmartScreen may warn on first run — verify the checksum before you allow it.

### Linux x86_64

**Download and verify**

```bash
VERSION=vX.Y.Z
BASE="https://github.com/Moonlark-Dev/FakeDecision/releases/download/$VERSION"
ASSET=FakeDecision-linux-x86_64.tar.gz

curl -fLO "$BASE/$ASSET"
curl -fLO "$BASE/$ASSET.sha256"
sha256sum -c "$ASSET.sha256"      # -> FakeDecision-linux-x86_64.tar.gz: OK

# wget works too:
# wget "$BASE/$ASSET" "$BASE/$ASSET.sha256" && sha256sum -c "$ASSET.sha256"
```

Do not continue if the checksum does not match.

**Extract and first run**

```bash
tar -xzf FakeDecision-linux-x86_64.tar.gz
cd FakeDecision-linux-x86_64
./fakedecision --version            # FakeDecision vX.Y.Z
./fakedecision --host 0.0.0.0 --port 8790 --data-dir ./data
```

On first start the server creates the SQLite database and the admin account, then prints the generated admin password **once**. Open `http://<host>:8790/admin` (public site: `/`, health check: `/healthz`). Pass `--admin-email` / `--admin-password` (or `FAKE_DECISION_ADMIN_EMAIL` / `FAKE_DECISION_ADMIN_PASSWORD`) to choose the credentials up front; `--init-only` initializes the database and prints the bootstrap credentials without starting the server.

Bind to `0.0.0.0` only when clients connect directly. Behind the Caddy proxy below, bind `127.0.0.1` instead.

**Run with systemd**

Create a service user and install the files outside the extraction directory:

```bash
sudo useradd --system --home-dir /var/lib/fakedecision --shell /usr/sbin/nologin fakedecision
sudo mkdir -p /opt/fakedecision
sudo cp -a FakeDecision-linux-x86_64/. /opt/fakedecision/
sudo install -d -o fakedecision -g fakedecision /var/lib/fakedecision
```

`/etc/systemd/system/fakedecision.service`:

```ini
[Unit]
Description=FakeDecision
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=fakedecision
Group=fakedecision
WorkingDirectory=/opt/fakedecision
ExecStart=/opt/fakedecision/fakedecision --host 127.0.0.1 --port 8790 --data-dir /var/lib/fakedecision
Restart=always
RestartSec=3
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

Initialize once so the generated password is printed to your terminal, then start the service:

```bash
sudo -u fakedecision /opt/fakedecision/fakedecision --init-only --data-dir /var/lib/fakedecision
sudo systemctl daemon-reload
sudo systemctl enable --now fakedecision
sudo systemctl status fakedecision
sudo journalctl -u fakedecision -f
```

If you skip `--init-only`, the generated password is logged as `BOOTSTRAP ADMIN CREATED` on the first start.

### Windows x86_64

**Download and verify**

```powershell
$Version = "vX.Y.Z"
$Base = "https://github.com/Moonlark-Dev/FakeDecision/releases/download/$Version"
$Asset = "FakeDecision-windows-x86_64.zip"

# Windows PowerShell 5.1: GitHub requires TLS 1.2.
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

Invoke-WebRequest "$Base/$Asset" -OutFile $Asset
Invoke-WebRequest "$Base/$Asset.sha256" -OutFile "$Asset.sha256"

$Expected = (Get-Content "$Asset.sha256" -Raw).Split()[0].ToLower()
$Actual = (Get-FileHash $Asset -Algorithm SHA256).Hash.ToLower()
if ($Actual -ne $Expected) { throw "SHA-256 mismatch for $Asset" }
"Checksum OK: $Actual"
```

**Extract and first run**

```powershell
Expand-Archive $Asset -DestinationPath .
cd FakeDecision-windows-x86_64
.\fakedecision.exe --version
.\fakedecision.exe --host 0.0.0.0 --port 8790 --data-dir .\data
```

The first start behaves as on Linux: the database and admin are created, and the generated password is printed **once**. Open `http://localhost:8790/admin`; `--admin-email` / `--admin-password` and `--init-only` work the same way.

**Run as a Windows service (NSSM)**

[NSSM](https://nssm.cc/download) is the simplest way to run the executable as a service; put `nssm.exe` on `PATH` or call it by full path. The commands assume the release was extracted to `C:\FakeDecision\FakeDecision-windows-x86_64`; adjust `$App` otherwise.

```powershell
$Root = "C:\FakeDecision"
$App = "$Root\FakeDecision-windows-x86_64"
New-Item -ItemType Directory -Force "$Root\data", "$Root\logs" | Out-Null

nssm install FakeDecision "$App\fakedecision.exe"
nssm set FakeDecision AppParameters "--host 127.0.0.1 --port 8790 --data-dir $Root\data"
nssm set FakeDecision AppDirectory $App
nssm set FakeDecision AppStdout "$Root\logs\fakedecision.out.log"
nssm set FakeDecision AppStderr "$Root\logs\fakedecision.err.log"
nssm set FakeDecision AppRotateFiles 1
nssm set FakeDecision Start SERVICE_AUTO_START
nssm set FakeDecision AppExit Default Restart
nssm set FakeDecision AppRestartDelay 3000
nssm start FakeDecision
```

To get the bootstrap password on the console instead of in `fakedecision.out.log`, initialize once before the service's first run:

```powershell
& "$App\fakedecision.exe" --init-only --data-dir "$Root\data"
```

If you expose the app directly on the LAN (for example with `--host 0.0.0.0`), allow port 8790 in the firewall (private profile only):

```powershell
New-NetFirewallRule -DisplayName "FakeDecision (LAN)" -Direction Inbound -Protocol TCP -LocalPort 8790 -Action Allow -Profile Private -RemoteAddress LocalSubnet
```

Skip that rule when only Caddy on the same machine talks to `127.0.0.1:8790`.

**Task Scheduler alternative**

```powershell
$Root = "C:\FakeDecision"
$App = "$Root\FakeDecision-windows-x86_64"
$Action = New-ScheduledTaskAction -Execute "$App\fakedecision.exe" `
  -Argument "--host 127.0.0.1 --port 8790 --data-dir $Root\data" -WorkingDirectory $App
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Seconds 0)
Register-ScheduledTask -TaskName "FakeDecision" -Action $Action -Trigger $Trigger -Settings $Settings -User "SYSTEM" -RunLevel Highest
```

### TLS reverse proxy

Terminate TLS in front of the app and keep the executable bound to loopback. [Caddy](https://caddyserver.com/) obtains and renews certificates automatically:

```caddyfile
fakedecision.example.com {
    encode zstd gzip
    reverse_proxy 127.0.0.1:8790
}
```

Start the app with `--host 127.0.0.1` and set the public origin explicitly, e.g. `--public-url https://fakedecision.example.com` (or `FAKE_DECISION_PUBLIC_URL`), so generated links and Origin checks use the public URL. Set `FAKE_DECISION_TRUST_PROXY=1` only when the app is behind a trusted proxy such as this Caddy instance. The same rule proxies the admin WebSocket. On Windows, put `--public-url` in the NSSM `AppParameters` / scheduled-task argument.

### Upgrade

Keep the data directory; replace only the program files.

```bash
# Linux
sudo systemctl stop fakedecision
# download and verify the new release as shown above, then:
sudo cp -a FakeDecision-linux-x86_64/. /opt/fakedecision/
sudo systemctl start fakedecision
sudo systemctl status fakedecision
```

```powershell
# Windows (NSSM)
nssm stop FakeDecision
# download and verify the new release, then replace C:\FakeDecision\FakeDecision-windows-x86_64
nssm start FakeDecision
```

The data directory (`/var/lib/fakedecision` in the systemd example, `C:\FakeDecision\data` above, or the bundled `./data` for a manual run) holds the SQLite database, the generated secret and the uploaded logo. Back it up before upgrading; the schema is initialized automatically on start, and existing data and the admin account are preserved.

### Branding

Site name, tagline, description and links are edited in **`/admin/settings`**. The same page accepts a logo upload — PNG, JPEG, WebP or SVG up to **512 KB** — stored in the data directory and also used as the site favicon. Changes take effect immediately; no rebuild or restart is required.

### Private use

The [legal warning](#legal-warning) at the top applies to release installs as well: FakeDecision is for private, local and research use only, and must not be presented as a real decision-model provider or offered as a public or commercial service. If you serve it over a LAN or behind the proxy above, restrict access to people entitled to use it — `robots.txt` and `X-Robots-Tag` discourage indexing but are not access control.

## Docker

```bash
cp .env.example .env
# edit .env; set FAKE_DECISION_ADMIN_PASSWORD or read the generated one from logs
docker compose up --build -d
docker compose logs -f
```

The container binds to `127.0.0.1:8790` by default. Put your own TLS reverse proxy in front of it if needed, set `FAKE_DECISION_PUBLIC_URL` and (only behind a trusted proxy) `FAKE_DECISION_TRUST_PROXY=1`.

## Configuration

All settings can be supplied as CLI flags or environment variables. Server address, port, database path and secret are **not** editable from the admin UI.

| Flag | Environment | Default | Notes |
| --- | --- | --- | --- |
| `--host` | `FAKE_DECISION_HOST` | `127.0.0.1` | Bind address |
| `--port` | `FAKE_DECISION_PORT` | `8790` | Bind port |
| `--data-dir` | `FAKE_DECISION_DATA_DIR` | `~/.local/share/fakedecision` | SQLite + generated secret |
| `--database` | `FAKE_DECISION_DATABASE` | `<data-dir>/fakedecision.sqlite3` | Explicit DB path |
| `--admin-email` | `FAKE_DECISION_ADMIN_EMAIL` | `admin@fakedecision.local` | First admin |
| `--admin-password` | `FAKE_DECISION_ADMIN_PASSWORD` | generated | Printed once |
| `--public-url` | `FAKE_DECISION_PUBLIC_URL` | empty | Origin used for Origin checks/links |
| `--secret` | `FAKE_DECISION_SECRET` | generated + persisted | Reserved server secret |
| `--cors-origin` | `FAKE_DECISION_CORS_ORIGINS` | none | Repeatable / comma-separated |
| `--log-level` | `FAKE_DECISION_LOG_LEVEL` | `info` | Uvicorn/application log level |
| `--dev` | — | off | Development mode flag |
| `--no-frontend` | `FAKE_DECISION_SERVE_FRONTEND=0` | serve | API-only mode |
| `--init-only` | — | — | Initialize DB, print credentials, exit |

Runtime product settings (site name, registration, timeout, auto-fill, model catalog, operator assignment, etc.) are managed in `/admin/settings`, `/admin/models` and `/admin/operators`. The site logo is uploaded in `/admin/settings` and stored in the data directory.

## How the human decision flow works

1. A client calls `POST /v1/systemone` or `POST /v1beta/decisions` with an API key.
2. The backend parses the protocol into a canonical shared input + typed questions and stores the request in SQLite.
3. A matching operator is selected among **online** back-office users assigned to that model (admins receive all requests when enabled). The request appears over WebSocket in `/admin/queue`.
4. The operator sees a human-readable rendering of the input and one editor per question:
   - **noul**: probability slider/number + quick presets; confidence derived from the winning side.
   - **choice**: pick a winner and edit per-option probabilities.
   - **score**: edit per-level probabilities; expected score is calculated from the distribution.
   - Per-question **Randomize** and whole-request **Randomize all** fill plausible, calibrated-looking data.
   - Drafts autosave to the server, so manual answers survive an auto-fill.
5. Submitting returns the answer in the exact provider response shape. The HTTP client never sees the human layer.
6. The request card shows the HTTP deadline and the auto-fill moment. If auto-fill is enabled, once the auto-fill deadline is reached the server preserves valid manual answers, generates the missing ones, and releases the HTTP request before the hard deadline. If it is disabled, the client receives a timeout error.

### Realistic random data

The generator is intentionally not uniform:

- `noul` draws from a human-ish mixture of decisive, leaning and uncertain probabilities, never exact 0/1.
- `choice` draws a confidence first, then distributes the remaining mass with a Dirichlet-like split. A high-confidence answer cannot be a near-uniform map; the runner-up is visibly behind.
- `score` draws a latent rating and uncertainty, then discretizes a skewed Gaussian over the ordered rubric; `score` is the probability-weighted expected level.
- Probabilities are normalized, rounded, and the selected choice is kept as the argmax. Tests assert these invariants over hundreds of samples.

## Provider API

### System One

```bash
curl -s http://localhost:8790/v1/systemone \
  -H "Authorization: Bearer fd_live_..." \
  -H "Content-Type: application/json" \
  -H "X-Decision-Timeout-Ms: 120000" \
  -d '{
    "model": "jev-latest",
    "state": {"ticket": "The same order was charged twice."},
    "questions": {
      "refund": {"type": "noul", "instructions": "Is this a refund request?"},
      "action": {"type": "choice", "instructions": "Choose an action.",
        "criteria": {"refund": "Refund it", "replace": "Replace it"}},
      "urgency": {"type": "score", "instructions": "How urgent?",
        "criteria": ["Low", "Medium", "High"]}
    }
  }'
```

### Gemini Decisions

```bash
curl -s http://localhost:8790/v1beta/decisions \
  -H "x-goog-api-key: fd_live_..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-decision-1",
    "input": [{"type": "text", "text": "A photo of a spill near the counter."}],
    "questions": {
      "spill": {"type": "noul", "instructions": "Is there a spill?"},
      "cleanup": {"type": "choice", "instructions": "Pick a cleanup action.",
        "criteria": {"wipe": "Wipe it", "janitor": "Call janitorial"}}
    }
  }'
```

Full request/response shapes, model listing, error behavior and management endpoints are documented in [`docs/API.md`](docs/API.md). The public docs are also available in the running app at `/docs`.

### SDK-like usage

The API is wire-compatible with common decision clients:

- System One requests/responses follow the native `/v1/systemone` contract (`model`, `state`, `questions`; keyed `answers`; `usage`; `rounding`).
- Google requests use `POST /v1beta/decisions` with `x-goog-api-key` and the `noul`/`choice`/`score` primitives.
- `POST /v1beta/models/{model}:decisions` is also accepted.

## API keys and accounts

- Users register on the public site, sign in, and create API keys in the console.
- Keys are stored as SHA-256 hashes; the plaintext secret is shown **once**.
- Revoked or disabled keys/accounts are rejected. Per-key rate limiting is configurable (default 90/min).
- There is no billing. Usage is a request count/history only.

## Admin / operator routing

- Admin creates ordinary back-office users in `/admin/operators`.
- Each operator can be assigned one or more model names. Requests for a model are offered only to operators assigned that model.
- Admins see all models. The setting **Admin receives all requests** controls whether an online admin can be selected for routing; they can always inspect and answer manually.
- Assignment prefers the least-busy online operator. If nobody is online, the request waits in the queue and is assigned on the next matching login. If an operator disconnects with an active request, it is returned to the queue/reassigned.
- Both roles receive a WebSocket event on assignment. The admin top bar has a sound toggle (persisted in the browser). Sound is generated with WebAudio and only plays for requests assigned to that operator.

## Development

```bash
# terminal 1: backend
FAKE_DECISION_DATA_DIR=./data PYTHONPATH=backend python -m fake_decision --dev --host 127.0.0.1 --port 8790

# terminal 2: frontend (proxies /api, /v1, /v1beta, WebSocket)
cd frontend && pnpm dev
```

Tests:

```bash
PYTHONPATH=backend python3 -m pytest -q     # 29 backend tests
cd frontend && pnpm exec vue-tsc --noEmit   # strict TS
```

Build:

```bash
cd frontend && pnpm build
bash scripts/build_executable.sh            # Nuitka standalone + tar.gz (Linux) / zip (Windows) + SHA256
```

## CI and releases

`.github/workflows/ci.yml` runs on pushes and pull requests:

1. Installs backend/frontend dependencies.
2. Typechecks and builds the Vue app.
3. Runs the backend test suite.
4. Builds a **Nuitka standalone Linux x86_64 executable** (no `--onefile`; faster startup, no TMPDIR unpack failure).
5. Verifies the binary starts and initializes a database.
6. Uploads `FakeDecision-linux-x86_64.tar.gz` and its `.sha256` as a workflow artifact.

`.github/workflows/release.yml` runs the same test/build pipeline on `v*` tags, additionally builds the Windows x86_64 executable and publishes all four files to the GitHub Release:

- `FakeDecision-linux-x86_64.tar.gz` and `FakeDecision-linux-x86_64.tar.gz.sha256`
- `FakeDecision-windows-x86_64.zip` and `FakeDecision-windows-x86_64.zip.sha256`

A manual `workflow_dispatch` run builds and verifies the executables **without** publishing a release. Both executables bundle the frontend static assets and need no Node/Python runtime at run time.

## Project layout

```
backend/fake_decision/
  app.py             FastAPI factory, middleware, static SPA hosting
  cli.py             CLI flags, startup warning, uvicorn runner
  db.py              SQLite schema and helpers
  protocols.py       System One / Google parsing, validation, response codecs
  randomize.py       realistic probability generator
  manager.py         request lifecycle, assignment, drafts, deadlines, auto-fill
  realtime.py        WebSocket fan-out
  routes/            public, auth/account, admin, provider API, WebSocket
  web/dist/          built Vue app (generated, not committed)
  tests/             pytest suite
frontend/src/
  public/            provider site
  console/           user console
  admin/             internal operations console
  components/        shared UI
  lib/               API client, session, theme, format, toasts
docs/                API and frontend contracts
scripts/             preview, build, smoke test
```

## Security notes

- Sessions are opaque random tokens stored hashed in SQLite; cookies are `HttpOnly`, `SameSite=Lax`, and `Secure` over HTTPS.
- Passwords use scrypt. API keys are hashed. Mutating cookie APIs reject cross-site `Origin`s. All responses carry CSP, frame, MIME and no-index headers.
- `robots.txt` disallows all user agents.
- This is a private-use application. Do not expose it to the public. See [`SECURITY.md`](SECURITY.md).

## License

GNU Affero General Public License v3.0 or later. See [`LICENSE`](LICENSE). No warranty; use at your own legal risk.
