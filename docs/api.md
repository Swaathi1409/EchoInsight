# API Reference

Base URL (dev): `http://localhost:8000`
All protected endpoints require `Authorization: Bearer <token>`.
All responses are JSON. Errors use `{"code": "...", "message": "...", "request_id": "..."}`.

---

## Authentication

### POST /api/v1/auth/login
Obtain a JWT access token.

**Request**
```json
{ "username": "admin", "password": "yourpassword" }
```

**Response 200**
```json
{ "access_token": "eyJ...", "token_type": "bearer" }
```

**Response 401** — wrong password.

---

## Conversations

### POST /api/v1/conversations
Create a new conversation. The system assigns an agent and team deterministically.

**Request**
```json
{ "channel": "call" }
```
`channel`: `call` | `chat` | `email`

**Response 201**
```json
{
  "id": "uuid",
  "agent_id": "agent_00",
  "team_id": "team_00",
  "channel": "call",
  "status": "active",
  "turn_count": 0,
  "analysis_version": 0,
  "started_at": "2024-01-01T00:00:00Z"
}
```

---

### GET /api/v1/conversations
List conversations visible to the caller (scope-filtered by role).

**Query parameters**
| Param | Default | Description |
|-------|---------|-------------|
| `limit` | 50 | Max results |
| `offset` | 0 | Pagination offset |
| `status` | — | Filter by `active` / `ended` |

**Response 200** — array of conversation summaries.

---

### GET /api/v1/conversations/{id}
Get full conversation detail including turns.

**Response 200**
```json
{
  "id": "uuid",
  "agent_id": "...",
  "team_id": "...",
  "status": "ended",
  "turn_count": 12,
  "analysis_version": 1,
  "turns": [...],
  "provisional_state": null,
  "analysis": null
}
```

**Response 403** — caller does not have permission for this conversation.
**Response 404** — conversation does not exist.

---

### POST /api/v1/conversations/{id}/turns
Append a turn to an active conversation.

**Request**
```json
{
  "speaker": "agent",
  "text": "Thank you for calling...",
  "idempotency_key": "client-unique-key"
}
```
- `speaker`: `agent` | `customer`
- `text`: max 32,000 characters
- `idempotency_key`: unique per-turn client-generated key

**Response 201** — new turn created.
**Response 200** — idempotent replay (same key); returns stored turn.
**Response 409** — conversation has ended.

**Response body**
```json
{
  "turn_id": "turn_0001",
  "seq": 1,
  "speaker": "agent",
  "text_redacted": "Thank you for calling Union Mobile, my name is [NAME].",
  "extraction_status": "queued",
  "provisional_state": null,
  "ledger": []
}
```

---

### POST /api/v1/conversations/{id}/end
End a conversation and queue the final analysis job.

**Request body**: empty `{}` or omit.

**Response 202**
```json
{
  "status": "ended",
  "conversation_id": "uuid",
  "job_id": "uuid"
}
```

**Response 409** — conversation is already ended.

---

### GET /api/v1/conversations/{id}/jobs
List jobs associated with a conversation.

**Response 200** — array of job records.
```json
[
  {
    "job_id": "uuid",
    "job_type": "final_analysis",
    "status": "queued",
    "attempts": 0,
    "created_at": "..."
  }
]
```

---

### GET /api/v1/conversations/open-commitments
List open commitments across all conversations visible to the caller.

**Query**: `limit` (default 50), `offset` (default 0)

**Response 200** — array of commitment records with `conversation_id`, `description`, `owner`, `deadline`, `status`.

---

### GET /api/v1/conversations/false-resolutions
List conversations where a false resolution was detected.

**Response 200** — array of conversation summaries with `false_resolution_reason`.

---

## Analytics

### GET /api/v1/analytics/agent/{agent_id}
Agent-level QA metrics. Callers with `agent` role can only access their own agent_id.

**Response 200**
```json
{
  "agent_id": "agent_00",
  "period_days": 30,
  "conversations_analyzed": 5,
  "avg_score": 87.4,
  "avg_coverage": 0.91,
  "false_resolutions": 1,
  "false_resolutions_count": 1,
  "open_commitments": 2
}
```

**Response 403** — agent trying to access another agent's analytics.

---

### GET /api/v1/analytics/team/{team_id}
Team-level QA metrics. `supervisor` role is scoped to their own team.

**Response 200** — same shape as agent analytics plus `agents_count`.

---

## Health

### GET /health
Liveness check. Returns 200 if the service is running.

**Response 200**
```json
{ "status": "ok", "version": "0.1.0" }
```

### GET /ready
Readiness check. Returns 200 only if DB is reachable and migrations are up to date.

**Response 200**
```json
{ "status": "ok", "database": "ok", "migrations": "ok" }
```

**Response 503** — database or migrations not ready.

---

## Error Codes

| HTTP Status | code | Meaning |
|-------------|------|---------|
| 400 | `bad_request` | Invalid input |
| 401 | `unauthorized` | Missing or invalid token |
| 403 | `forbidden` | Authenticated but not authorized for this resource |
| 404 | `not_found` | Resource does not exist |
| 409 | `conflict` | State conflict (e.g. ended conversation) |
| 422 | `validation_error` | Request body failed Pydantic validation |
| 500 | `internal_error` | Unhandled server error (details not exposed) |

---

## Rate Limits

No server-side rate limiting is implemented in this version.
For production, add rate limiting on `/api/v1/auth/login` at the reverse proxy level (e.g., Nginx `limit_req`).

---

## Notes

- All timestamps are ISO 8601 UTC.
- All IDs are UUIDs except `turn_id` (zero-padded sequential: `turn_0001`).
- PII is redacted before storage; the original text is never returned.
- Analysis jobs run asynchronously. Poll `GET /conversations/{id}` or `GET /conversations/{id}/jobs` for status.
- Full interactive API docs available at `/docs` (development only; disabled in production).
