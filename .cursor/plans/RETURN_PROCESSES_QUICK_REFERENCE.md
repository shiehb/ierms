# Return Inspection Processes - Quick Reference Guide

This is a quick reference guide for all return inspection actions. For detailed documentation, see [RETURN_PROCESSES_DOCUMENTATION.md](./RETURN_PROCESSES_DOCUMENTATION.md).

## Quick Lookup Table

| Action | Who | From Status | To Status | Remarks | Endpoint |
|--------|-----|------------|-----------|---------|----------|
| `return_to_previous` | Monitoring Personnel, Unit Head | `MONITORING_ASSIGNED`, `UNIT_ASSIGNED` | `UNIT_ASSIGNED`, `SECTION_ASSIGNED` | Optional | `POST /api/inspections/{id}/return_to_previous/` |
| `return_to_monitoring` | Unit Head, Section Chief | `MONITORING_COMPLETED_COMPLIANT`, `MONITORING_COMPLETED_NON_COMPLIANT` | `MONITORING_IN_PROGRESS` | **Required** | `POST /api/inspections/{id}/return_to_monitoring/` |
| `return_to_unit` | Section Chief | `UNIT_REVIEWED`, `UNIT_COMPLETED_*`, `MONITORING_COMPLETED_*` | `UNIT_IN_PROGRESS`, `MONITORING_IN_PROGRESS` | **Required** | `POST /api/inspections/{id}/return_to_unit/` |
| `return_to_section` | Division Chief | `DIVISION_REVIEWED`, `SECTION_REVIEWED`, `SECTION_COMPLETED_*` | `SECTION_IN_PROGRESS`, `UNIT_REVIEWED/COMPLETED_*`, `MONITORING_IN_PROGRESS` | **Required** | `POST /api/inspections/{id}/return_to_section/` |
| `return_to_division` | Legal Unit | `LEGAL_REVIEW` | `DIVISION_REVIEWED` | Optional | `POST /api/inspections/{id}/return_to_division/` |

## Workflow Decision Tree

### When to Use Each Return Action

```
┌─────────────────────────────────────────────────────────────┐
│ Need to return an inspection?                                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       ▼
  Early Stage?                          Review Stage?
  (ASSIGNED status)                     (COMPLETED/REVIEWED)
        │                                       │
        ▼                                       ▼
  return_to_previous              ┌─────────────┴─────────────┐
                                 │                           │
                                 ▼                           ▼
                        Unit Head reviewing?        Section Chief reviewing?
                                 │                           │
                                 ▼                           ▼
                        return_to_monitoring        return_to_unit
                                 │                           │
                                 ▼                           ▼
                        Division Chief reviewing?    Legal Unit reviewing?
                                 │                           │
                                 ▼                           ▼
                        return_to_section            return_to_division
```

## Status Flow Diagrams

### return_to_previous
```
MONITORING_ASSIGNED → UNIT_ASSIGNED (if unit exists)
                   → SECTION_ASSIGNED (if no unit or target="section")

UNIT_ASSIGNED → SECTION_ASSIGNED
```

### return_to_monitoring
```
MONITORING_COMPLETED_* → MONITORING_IN_PROGRESS
```

### return_to_unit
```
UNIT_REVIEWED → MONITORING_COMPLETED_* → MONITORING_IN_PROGRESS
UNIT_COMPLETED_* → UNIT_IN_PROGRESS
MONITORING_COMPLETED_* (no unit) → MONITORING_IN_PROGRESS
```

### return_to_section
```
DIVISION_REVIEWED → SECTION_IN_PROGRESS
SECTION_REVIEWED → UNIT_REVIEWED/COMPLETED_* (if unit exists)
                 → MONITORING_COMPLETED_* → MONITORING_IN_PROGRESS (if no unit)
SECTION_COMPLETED_* → SECTION_IN_PROGRESS
```

### return_to_division
```
LEGAL_REVIEW → DIVISION_REVIEWED
```

## Code Locations

### Backend
- **Main Implementation**: `server/inspections/views.py`
  - `return_to_previous`: lines 1051-1165
  - `return_to_monitoring`: lines 2022-2075
  - `return_to_unit`: lines 2077-2186
  - `return_to_section`: lines 2189-2364
  - `return_to_division`: lines 3574-3633
  - `_execute_return_transition()`: lines 1948-2020 (helper method)

- **Available Actions Mapping**: `server/inspections/serializers.py` (lines 276-324)

### Frontend
- **Action Handlers**: `src/hooks/useInspectionActions.js`
- **API Services**: `src/services/api.js`
- **UI Components**: `src/pages/InspectionReviewPage.jsx`
- **Action Constants**: `src/constants/inspectionConstants.js`

## Common Patterns

### All Return Actions:
1. Validate user permissions
2. Validate source status
3. Find assignee (from history or default)
4. Transition status
5. Create history entry
6. Send notification
7. Create audit trail

### Remarks Handling:
- **Required**: `return_to_monitoring`, `return_to_unit`, `return_to_section`
- **Optional with default**: `return_to_previous`, `return_to_division`

### Assignee Resolution:
- Priority: History-based assignment → Default assignment
- Uses `_get_stage_assignee()` for most actions
- Uses `get_next_assignee()` for `return_to_previous` and `return_to_division`

## Error Codes

| Error | Status Code | Meaning |
|-------|------------|---------|
| Invalid user level | 403 Forbidden | User doesn't have permission |
| Invalid status | 400 Bad Request | Cannot return from current status |
| Missing assignee | 404 Not Found | No appropriate assignee found |
| Missing remarks | 400 Bad Request | Remarks required but not provided |
| Invalid workflow | 400 Bad Request | Workflow validation failed |

## Testing Checklist

When testing return actions, verify:
- [ ] User permission validation
- [ ] Status validation
- [ ] Assignee resolution (history vs default)
- [ ] Status transition
- [ ] History entry creation
- [ ] Notification sent
- [ ] Audit trail created
- [ ] Remarks handling (required vs optional)
- [ ] Error handling for invalid scenarios

## Common Use Cases

1. **Unit Head finds issues in monitoring work** → `return_to_monitoring`
2. **Section Chief needs unit rework** → `return_to_unit`
3. **Division Chief needs corrections** → `return_to_section`
4. **Legal Unit needs clarification** → `return_to_division`
5. **Wrong assignment made** → `return_to_previous`

---

*For detailed documentation, see [RETURN_PROCESSES_DOCUMENTATION.md](./RETURN_PROCESSES_DOCUMENTATION.md)*

