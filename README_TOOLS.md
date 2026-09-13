# Phase 1 Controlled Agent Tools

Tools are the only application boundary through which an LLM-facing agent can request database operations.

## Tool contract

Each tool accepts a JSON-compatible dictionary and returns:

```json
{
  "success": true,
  "data": {}
}
```

or:

```json
{
  "success": false,
  "error": {
    "code": "SLOT_UNAVAILABLE",
    "message": "Requested schedule slot is not available.",
    "retryable": true,
    "details": {"schedule_id": 123}
  }
}
```

## Tools

### get_doctors
Input:
```json
{"clinic_id":"CLINIC-001"}
```

Returns active doctors for the clinic.

### get_services
Input:
```json
{"clinic_id":"CLINIC-001"}
```

Returns active services, duration and fee.

### check_availability
Required:
- `clinic_id`
- `doctor_id`
- `service_id`
- `start_at`

Optional:
- `end_at`
- `limit`

Only `doctor_schedules.status = 'available'` rows are returned. No LLM-generated availability is possible.

### book_appointment
Requires:
- clinic
- doctor
- service
- patient
- exact `schedule_id`
- unique appointment ID

Before committing, it verifies:
1. clinic exists
2. doctor belongs to clinic and is active
3. service belongs to clinic and is active
4. patient belongs to clinic and is active
5. doctor provides the service
6. exact schedule belongs to doctor/clinic
7. schedule is still available
8. schedule duration is sufficient
9. database transaction/constraint accepts the booking

## Agent boundary

The LLM should receive only these structured tool definitions. It must not receive a database connection, SQL executor, ORM session, filesystem database path, or unrestricted query capability.

Recommended flow:

`intent -> get_doctors/get_services -> check_availability -> book_appointment`

The agent must never report a booking or availability claim unless the corresponding tool returned `success=true`.
