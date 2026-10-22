# API Contract Summary

Base prefix: `/v1`. JSON request/response bodies. Authenticated routes require `Authorization: Bearer <access-token>`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health/live` | Liveness check |
| GET | `/health/ready` | DB readiness check |
| POST | `/v1/auth/demo` | Local-only demo session token |
| POST | `/v1/onboarding` | Provision first household/profile for verified identity |
| GET | `/v1/me` | Current profile and household |
| GET | `/v1/sports/events` | Event list; sample fixture is clearly labelled |
| GET | `/v1/sports/events/{event_id}` | Event details |
| GET | `/v1/sports/events/{event_id}/timeline` | Event timeline |
| GET | `/v1/sports/events/{event_id}/tactical` | Field and player nodes |
| POST | `/v1/sessions` | Create viewing session |
| GET | `/v1/sessions/{session_id}` | Read session in caller's household |
| PATCH | `/v1/households/{household_id}/preferences` | Update current profile preferences in that household |
| POST | `/v1/experience/resolve` | Explainable mode recommendation or user override |
| POST | `/v1/ai/commands` | Analyze a command against a selected event |
| POST | `/v1/coach/sessions` | Start a consented coaching session |
| POST | `/v1/coach/sessions/{session_id}/metrics` | Store derived metrics only |
| PATCH | `/v1/coach/sessions/{session_id}/complete` | Complete coach session |
| POST | `/v1/feedback` | Submit UX/bug/data-quality feedback |
| DELETE | `/v1/me/data` | Delete household application data |

## Error envelope

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Event not found",
    "request_id": "req_abc123",
    "retryable": false
  }
}
```

Do not expose database exception messages, provider credentials, stack traces or raw model prompts in public errors.
