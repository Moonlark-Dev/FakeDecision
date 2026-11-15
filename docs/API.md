# API contract

All timestamps are Unix milliseconds unless noted. Management endpoints live under `/api` and use HttpOnly session cookies. Provider endpoints are `/v1/systemone` (System One / TypeSafe-compatible) and `/v1beta/decisions` (Google Gemini Decisions-compatible).

## Provider authentication

- System One: `Authorization: Bearer fd_live_...`
- Gemini Decisions: `x-goog-api-key: fd_live_...` (Bearer also accepted)
- API keys are created in the user console. Only a hash is stored; a new secret is shown once.

## System One — `POST /v1/systemone`

Request:

```json
{
  "model": "jev-latest",
  "state": "The customer was charged twice.",
  "questions": {
    "refund": {
      "type": "noul",
      "instructions": "Does the customer ask for a refund?",
      "criteria": { "true": "Explicit refund request", "false": "No request" }
    },
    "action": {
      "type": "choice",
      "instructions": "Pick the next action.",
      "criteria": {
        "refund": "Refund the duplicate charge",
        "replace": "Send a replacement"
      }
    },
    "urgency": {
      "type": "score",
      "instructions": "How urgent is this?",
      "criteria": ["Low", "Medium", "High"]
    }
  }
}
```

Response:

```json
{
  "model": "jev-latest",
  "answers": {
    "refund": { "type": "noul", "noul": 0.91 },
    "action": {
      "type": "choice", "choice": "refund",
      "probabilities": { "refund": 0.88, "replace": 0.12 }, "confidence": 0.88
    },
    "urgency": {
      "type": "score", "score": 1.64,
      "probabilities": { "0": 0.07, "1": 0.22, "2": 0.71 },
      "confidence": 0.71, "legend": { "0": "Low", "1": "Medium", "2": "High" }
    }
  },
  "usage": { "input_tokens": 48, "output_tokens": 0 },
  "rounding": { "probabilityDecimals": 2, "scoreDecimals": 2 }
}
```

`boolean` is accepted as an alias for `noul`. A request may set `X-Decision-Timeout-Ms` (or `X-Request-Timeout-Ms`) to shorten the human response window.

## Gemini Decisions — `POST /v1beta/decisions`

Header `x-goog-api-key`. Body `model`, `input` (string or content-block array), `questions` with `type` `noul|choice|score`, `instructions`, `criteria`. Response:

```json
{
  "answers": {
    "refund": { "type": "noul", "noul": 0.91, "confidence": 0.91 },
    "action": {
      "type": "choice", "choice": "refund",
      "probabilities": { "refund": 0.88, "replace": 0.12 }, "confidence": 0.88
    },
    "urgency": {
      "type": "score", "score": 1.64,
      "probabilities": { "0": 0.07, "1": 0.22, "2": 0.71 },
      "confidence": 0.71, "legend": { "0": "Low", "1": "Medium", "2": "High" }
    }
  }
}
```

Also accepted: `POST /v1beta/models/{model}:decisions` and `POST /v1/decisions`.

## Provider model listing

- `GET /v1/models` → `{ object: "list", data: [{ id, object, ... }] }`
- `GET /v1beta/models` → `{ models: [{ name: "models/…", displayName, ... }] }`

## Public site

- `GET /api/site` → `{ site_name, logo_url, tagline, description, announcement, registration_enabled, support_email, sound_default, show_register_cta, version }`
- `GET /api/branding/logo` → uploaded brand logo (`404` when the built-in mark is in use). Served with a versioned `?v=` query from `logo_url`.
- `GET /api/models` → `{ models: Model[] }`
- `GET /api/status`

## User session

- `POST /api/auth/register` `{email,name,password}` → `{user}`
- `POST /api/auth/login` `{email,password}` → `{user}`
- `POST /api/auth/logout`
- `GET /api/auth/session` → `{user, admin}`
- `GET /api/account`
- `PATCH /api/account` `{name}`
- `POST /api/account/password` `{current_password,new_password}`
- `GET /api/keys` → `{keys}`
- `POST /api/keys` `{name}` → `{key, secret}`
- `DELETE /api/keys/{id}`
- `GET /api/account/usage?days=30`
- `GET /api/console/models`
- `POST /api/console/playground` `{protocol, model, input, questions, timeout_ms?}` → `{request_id, protocol, model, response, elapsed_ms}`

## Admin session

- `POST /api/admin/auth/login` `{email,password}` → `{admin}`
- `POST /api/admin/auth/logout`
- `GET /api/admin/auth/session` → `{admin, version}`
- `GET /api/admin/me`
- `POST /api/admin/account/password`

## Admin dashboard

- `GET /api/admin/overview`
- `GET /api/admin/requests?view=active|history|all&status=&model=&q=&limit=&offset=`
- `GET /api/admin/requests/{id}`
- `POST /api/admin/requests/{id}/answer` `{answers: Record<questionId, Answer>}`
- `PUT /api/admin/requests/{id}/draft` `{answers}`
- `POST /api/admin/requests/{id}/randomize` `{question_ids?: string[]}` → `{answers}`
- `PUT /api/admin/requests/{id}/assign` `{operator_id: string|null}` (admin only)
- `POST /api/admin/requests/{id}/cancel` (admin only)
- `GET /api/admin/operators`
- `POST /api/admin/operators` `{email,name,password,models[]}`
- `PATCH /api/admin/operators/{id}` `{name?,disabled?,password?,models?}`
- `GET /api/admin/users?q=&limit=&offset=`
- `GET /api/admin/users/{id}`
- `PATCH /api/admin/users/{id}` `{name?,disabled?,password?}`
- `GET /api/admin/models`
- `POST /api/admin/models` `{name,display_name,protocol,description,context_window,enabled,sort_order}`
- `PATCH /api/admin/models/{id}`
- `DELETE /api/admin/models/{id}`
- `GET /api/admin/settings` → `{values, version, limits}`
- `PUT /api/admin/settings` `{values}`
- `POST /api/admin/branding/logo` `{filename, data}` — `data` is a base64 data URL (PNG/JPEG/WebP/SVG, ≤512 KB); returns `{logo_url, bytes}`
- `DELETE /api/admin/branding/logo` — remove the custom logo, fall back to the built-in mark
- `GET /api/admin/audit?limit=&offset=`
- `GET /api/admin/export/requests`
- `GET /api/admin/presence`

## WebSocket — `/api/admin/ws`

Cookie-authenticated. Server messages:

```json
{ "type": "hello", "data": { "admin": {}, "server_time": 0, "pending": [], "presence": [], "settings": {} } }
{ "type": "request.created", "data": { "request": {}, "notify": true } }
{ "type": "request.assigned", "data": { "request": {}, "notify": true } }
{ "type": "request.updated", "data": { "request": {}, "notify": false } }
{ "type": "request.completed", "data": { "request": {}, "notify": true } }
{ "type": "presence", "data": { "operators": [] } }
{ "type": "ping", "data": { "time": 0 } }
```

`notify: true` means this connection's operator owns the request and should play the notification sound / raise a toast. The socket reconnects automatically and the REST snapshot is authoritative.

## Answer shapes

```ts
type NoulAnswer = { type: 'noul'; noul: number; confidence?: number }
type ChoiceAnswer = { type: 'choice'; choice: string; probabilities: Record<string, number>; confidence: number }
type ScoreAnswer = { type: 'score'; score: number; probabilities: Record<string, number>; confidence: number; legend?: Record<string, string> }
```

`noul` is P(true) in `[0.01, 0.99]`; `confidence = max(p, 1-p)`. Choice `choice` must be the argmax of `probabilities`; score is the probability-weighted expected level. The backend validates and repairs small rounding drift, but rejects contradictions.

## Human timing

- `created_at` + `timeout_seconds` → `deadline_at` (hard deadline).
- `auto_fill_at` is when the server will fill any missing answers and release the HTTP request, when the setting is enabled. The operator UI should show both countdowns.
- A draft is autosaved so manual answers survive the timeout auto-fill.
