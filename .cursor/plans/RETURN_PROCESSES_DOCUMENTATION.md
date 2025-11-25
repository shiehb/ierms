# Return Inspection Processes Documentation

This document provides comprehensive documentation for all return inspection actions in the Integrated Establishments Regulatory Management System. Return actions allow authorized users to send inspections back to previous stages in the workflow for corrections or rework.

## Table of Contents

1. [return_to_previous](#1-return_to_previous)
2. [return_to_monitoring](#2-return_to_monitoring)
3. [return_to_unit](#3-return_to_unit)
4. [return_to_section](#4-return_to_section)
5. [return_to_division](#5-return_to_division)
6. [Common Return Workflow](#common-return-workflow)

---

## 1. return_to_previous

### Action Name & Endpoint
- **Action**: `return_to_previous`
- **Endpoint**: `POST /api/inspections/{id}/return_to_previous/`
- **Code Location**: `server/inspections/views.py` (lines 1051-1165)

### Who Can Use It
- **Monitoring Personnel** (from `MONITORING_ASSIGNED` status)
- **Unit Head** (from `MONITORING_ASSIGNED` or `UNIT_ASSIGNED` status)

### Valid Source Statuses
- `MONITORING_ASSIGNED`
- `UNIT_ASSIGNED`

### Target Status
The target status depends on the current status and workflow history:

**From `MONITORING_ASSIGNED`:**
- Returns to `UNIT_ASSIGNED` (if unit stage exists in history)
- Returns to `SECTION_ASSIGNED` (if no unit stage, or if explicitly requested via `target: "section"`)

**From `UNIT_ASSIGNED`:**
- Returns to `SECTION_ASSIGNED`

### Assignee Logic
- Uses inspection history to find the previous assignee
- Falls back to `get_next_assignee()` if no history entry found
- For `UNIT_ASSIGNED` → `SECTION_ASSIGNED`: Falls back to Section Chief if no Unit Head available

### Workflow Logic
1. **From `MONITORING_ASSIGNED`:**
   - Checks history for previous `UNIT_ASSIGNED` or `SECTION_ASSIGNED` status
   - If history found: Uses that status and assignee
   - If no history: Uses request parameter `target` ("unit" or "section") to determine destination
   - Default: Returns to `UNIT_ASSIGNED`

2. **From `UNIT_ASSIGNED`:**
   - Always returns to `SECTION_ASSIGNED`
   - Finds Section Chief from history or uses default assignment

### Requirements
- **Remarks**: Optional (auto-generated if not provided)
- **Validation**: Must pass `can_transition_to()` check
- **Error Handling**: Returns error if no assignee found

### Frontend Availability
- Available in `InspectionsList.jsx` for Monitoring Personnel and Unit Head
- Shown when status is `MONITORING_ASSIGNED` or `UNIT_ASSIGNED`
- Action handler: `src/hooks/useInspectionActions.js` (line 86)
- API service: `src/services/api.js` (via `returnInspection`)

### Example Use Case
A Unit Head receives a monitoring assignment but realizes the inspection should have been assigned to a different section. They use `return_to_previous` to send it back to the Section Chief for reassignment.

### Workflow Diagram

```text
MONITORING_ASSIGNED
    ↓ (return_to_previous)
    ├─→ UNIT_ASSIGNED (if unit stage exists)
    └─→ SECTION_ASSIGNED (if no unit stage or target="section")

UNIT_ASSIGNED
    ↓ (return_to_previous)
    └─→ SECTION_ASSIGNED
```

---

## 2. return_to_monitoring

### Action Name & Endpoint
- **Action**: `return_to_monitoring`
- **Endpoint**: `POST /api/inspections/{id}/return_to_monitoring/`
- **Code Location**: `server/inspections/views.py` (lines 2022-2075)

### Who Can Use It
- **Unit Head** (primary user)
- **Section Chief** (when status is `UNIT_REVIEWED`)

### Valid Source Statuses
- `MONITORING_COMPLETED_COMPLIANT`
- `MONITORING_COMPLETED_NON_COMPLIANT`

### Target Status
- `MONITORING_IN_PROGRESS`

### Assignee Logic
- Finds Monitoring Personnel from inspection history
- Searches for assignee in monitoring stage statuses: `MONITORING_COMPLETED_*`, `MONITORING_IN_PROGRESS`, `MONITORING_ASSIGNED`
- Uses `_get_stage_assignee()` with `expected_userlevel='Monitoring Personnel'`
- Assignment based on inspection's law/section

### Workflow Logic
1. Validates user is Unit Head (or Section Chief at `UNIT_REVIEWED`)
2. Validates current status is a monitoring completed status
3. Requires remarks (cannot be empty)
4. Finds appropriate Monitoring Personnel assignee
5. Transitions status to `MONITORING_IN_PROGRESS`
6. Creates history entry with return label: "Returned to Monitoring Personnel"
7. Sends notification to assignee
8. Creates audit trail

### Requirements
- **Remarks**: **Required** (must not be empty)
- **User Level**: Unit Head (or Section Chief at `UNIT_REVIEWED`)
- **Status Validation**: Must be `MONITORING_COMPLETED_COMPLIANT` or `MONITORING_COMPLETED_NON_COMPLIANT`

### Frontend Availability
- Available for **Unit Head** when status is:
  - `MONITORING_COMPLETED_COMPLIANT`
  - `MONITORING_COMPLETED_NON_COMPLIANT`
- Available for **Section Chief** when status is `UNIT_REVIEWED`
- UI Location: `src/pages/InspectionReviewPage.jsx` (lines 994-1001)
- Action handler: `src/hooks/useInspectionActions.js` (line 91)
- API service: `src/services/api.js` (line 510)
- Success message: "Inspection returned to monitoring successfully!"

### Example Use Case
A Unit Head reviews a monitoring-completed inspection and finds issues that need correction. They return it to Monitoring Personnel with remarks explaining what needs to be fixed.

### Workflow Diagram

```text
MONITORING_COMPLETED_COMPLIANT / MONITORING_COMPLETED_NON_COMPLIANT
    ↓ (return_to_monitoring by Unit Head)
    └─→ MONITORING_IN_PROGRESS
        (Assigned to: Monitoring Personnel)
```

---

## 3. return_to_unit

### Action Name & Endpoint
- **Action**: `return_to_unit`
- **Endpoint**: `POST /api/inspections/{id}/return_to_unit/`
- **Code Location**: `server/inspections/views.py` (lines 2077-2186)

### Who Can Use It
- **Section Chief** only

### Valid Source Statuses
- `UNIT_REVIEWED`
- `UNIT_COMPLETED_COMPLIANT`
- `UNIT_COMPLETED_NON_COMPLIANT`
- `MONITORING_COMPLETED_COMPLIANT` (only if no unit stage exists)
- `MONITORING_COMPLETED_NON_COMPLIANT` (only if no unit stage exists)

### Target Status
The target status depends on the current status:

**From `UNIT_REVIEWED`:**
- Returns to the previous monitoring completion status (`MONITORING_COMPLETED_COMPLIANT` or `MONITORING_COMPLETED_NON_COMPLIANT`)
- Then transitions to `MONITORING_IN_PROGRESS`

**From `UNIT_COMPLETED_*`:**
- Returns to `UNIT_IN_PROGRESS`

**From `MONITORING_COMPLETED_*` (no unit stage):**
- Returns to `MONITORING_IN_PROGRESS`
- Only allowed if inspection never went through unit stage

### Assignee Logic
- **From `UNIT_REVIEWED`**: Finds Monitoring Personnel from history
- **From `UNIT_COMPLETED_*`**: Finds Unit Head from history or default assignment
- **From `MONITORING_COMPLETED_*`**: Finds Monitoring Personnel from history
- Uses `_get_stage_assignee()` with appropriate `expected_userlevel`

### Workflow Logic
1. **From `UNIT_REVIEWED`:**
   - Finds last monitoring completion status from history
   - Restores that status, then transitions to `MONITORING_IN_PROGRESS`
   - Assigns to Monitoring Personnel
   - Return label: "Returned to Monitoring Personnel"

2. **From `UNIT_COMPLETED_*`:**
   - Returns directly to `UNIT_IN_PROGRESS`
   - Assigns to Unit Head
   - Return label: "Returned to Unit Head"

3. **From `MONITORING_COMPLETED_*` (no unit stage):**
   - Validates that no unit stage history exists
   - Returns to `MONITORING_IN_PROGRESS`
   - Assigns to Monitoring Personnel
   - Return label: "Returned to Monitoring Personnel"
   - Error if unit history exists (prevents invalid workflow)

### Requirements
- **Remarks**: **Required** (must not be empty)
- **User Level**: Section Chief only
- **Status Validation**: Must be one of the valid source statuses
- **History Check**: For `MONITORING_COMPLETED_*`, validates no unit stage exists

### Frontend Availability
- Available for **Section Chief** when status is:
  - `UNIT_REVIEWED`
  - `UNIT_COMPLETED_COMPLIANT`
  - `UNIT_COMPLETED_NON_COMPLIANT`
- UI Location: `src/pages/InspectionReviewPage.jsx` (lines 1031-1038)
- Action handler: `src/hooks/useInspectionActions.js` (line 96)
- API service: `src/services/api.js` (line 525)
- Success message: "Inspection returned to unit successfully!"

### Example Use Case
A Section Chief reviews a unit-completed inspection and finds that the Unit Head missed important details. They return it to the Unit Head for rework with specific remarks about what needs correction.

### Workflow Diagram

```text
UNIT_REVIEWED
    ↓ (return_to_unit by Section Chief)
    └─→ MONITORING_COMPLETED_* → MONITORING_IN_PROGRESS
        (Assigned to: Monitoring Personnel)

UNIT_COMPLETED_COMPLIANT / UNIT_COMPLETED_NON_COMPLIANT
    ↓ (return_to_unit by Section Chief)
    └─→ UNIT_IN_PROGRESS
        (Assigned to: Unit Head)

MONITORING_COMPLETED_* (no unit stage)
    ↓ (return_to_unit by Section Chief)
    └─→ MONITORING_IN_PROGRESS
        (Assigned to: Monitoring Personnel)
```

---

## 4. return_to_section

### Action Name & Endpoint
- **Action**: `return_to_section`
- **Endpoint**: `POST /api/inspections/{id}/return_to_section/`
- **Code Location**: `server/inspections/views.py` (lines 2189-2364)

### Who Can Use It
- **Division Chief** only

### Valid Source Statuses
- `DIVISION_REVIEWED`
- `SECTION_REVIEWED`
- `SECTION_COMPLETED_COMPLIANT`
- `SECTION_COMPLETED_NON_COMPLIANT`

### Target Status
The target status depends on the current status and workflow history:

**From `DIVISION_REVIEWED`:**
- Returns to `SECTION_IN_PROGRESS`
- Assigns to Section Chief (from history or default)

**From `SECTION_REVIEWED`:**
- **If unit stage exists in history**: Returns to `UNIT_REVIEWED` or `UNIT_COMPLETED_*`
- **If no unit stage exists**: Returns to `MONITORING_COMPLETED_*` → `MONITORING_IN_PROGRESS`

**From `SECTION_COMPLETED_*`:**
- Returns to `SECTION_IN_PROGRESS`
- Assigns to Section Chief

### Assignee Logic
- **From `DIVISION_REVIEWED`**: Finds Section Chief from history (who forwarded it) or default assignment
- **From `SECTION_REVIEWED`**:
  - If unit exists: Finds Unit Head from history
  - If no unit: Finds Monitoring Personnel from history
- **From `SECTION_COMPLETED_*`**: Finds Section Chief from history or default assignment
- Uses `_get_stage_assignee()` with appropriate `expected_userlevel`

### Workflow Logic
1. **From `DIVISION_REVIEWED`:**
   - Finds last Section Chief who reviewed/forwarded the inspection
   - Returns to `SECTION_IN_PROGRESS`
   - Assigns to that Section Chief (or default if not found)
   - Return label: "Returned to Section Chief"

2. **From `SECTION_REVIEWED`:**
   - Checks history for unit stage (`UNIT_REVIEWED` or `UNIT_COMPLETED_*`)
   - **If unit stage exists:**
     - Returns to `UNIT_REVIEWED` (if that was last unit status)
     - OR returns to `UNIT_COMPLETED_*` (if that was last unit status)
     - Assigns to Unit Head
     - Return label: "Returned to Unit Head"
   - **If no unit stage:**
     - Finds last monitoring completion status from history
     - Restores that status, then transitions to `MONITORING_IN_PROGRESS`
     - Assigns to Monitoring Personnel
     - Return label: "Returned to Monitoring Personnel"
     - Error if monitoring entry not found

3. **From `SECTION_COMPLETED_*`:**
   - Returns to `SECTION_IN_PROGRESS`
   - Assigns to Section Chief
   - Return label: "Returned to Section Chief"

### Requirements
- **Remarks**: **Required** (must not be empty)
- **User Level**: Division Chief only
- **Status Validation**: Must be one of the valid source statuses
- **History Dependency**: Uses inspection history to determine appropriate return target

### Frontend Availability
- Available for **Division Chief** when status is:
  - `DIVISION_REVIEWED`
  - `SECTION_REVIEWED`
- UI Location: `src/pages/InspectionReviewPage.jsx` (referenced in action handlers)
- Action handler: `src/hooks/useInspectionActions.js` (line 101)
- API service: `src/services/api.js` (line 540)
- Success message: "Inspection returned to Section Chief with remarks."

### Example Use Case
A Division Chief reviews an inspection that was forwarded from Section and finds that it needs significant corrections. They return it to the Section Chief (or further down to Unit/Monitoring if appropriate) with detailed remarks about what needs to be addressed.

### Workflow Diagram

```text
DIVISION_REVIEWED
    ↓ (return_to_section by Division Chief)
    └─→ SECTION_IN_PROGRESS
        (Assigned to: Section Chief)

SECTION_REVIEWED
    ↓ (return_to_section by Division Chief)
    ├─→ UNIT_REVIEWED / UNIT_COMPLETED_* (if unit stage exists)
    │   (Assigned to: Unit Head)
    └─→ MONITORING_COMPLETED_* → MONITORING_IN_PROGRESS (if no unit stage)
        (Assigned to: Monitoring Personnel)

SECTION_COMPLETED_COMPLIANT / SECTION_COMPLETED_NON_COMPLIANT
    ↓ (return_to_section by Division Chief)
    └─→ SECTION_IN_PROGRESS
        (Assigned to: Section Chief)
```

---

## 5. return_to_division

### Action Name & Endpoint
- **Action**: `return_to_division`
- **Endpoint**: `POST /api/inspections/{id}/return_to_division/`
- **Code Location**: `server/inspections/views.py` (lines 3574-3633)

### Who Can Use It
- **Legal Unit** only

### Valid Source Statuses
- `LEGAL_REVIEW` only

### Target Status
- `DIVISION_REVIEWED`

### Assignee Logic
- Uses `inspection.get_next_assignee('DIVISION_REVIEWED')` to find Division Chief
- Returns error if no Division Chief found

### Workflow Logic
1. Validates user is Legal Unit
2. Validates current status is `LEGAL_REVIEW`
3. Finds Division Chief assignee
4. Transitions status from `LEGAL_REVIEW` to `DIVISION_REVIEWED`
5. Assigns to Division Chief
6. Creates history entry with remarks (default: "Returned to Division Chief by Legal Unit")
7. Creates audit trail

### Requirements
- **Remarks**: Optional (defaults to "Returned to Division Chief by Legal Unit")
- **User Level**: Legal Unit only
- **Status Validation**: Must be `LEGAL_REVIEW`
- **Assignee Validation**: Must have an active Division Chief

### Frontend Availability
- Available for **Legal Unit** when status is `LEGAL_REVIEW`
- UI Location: `src/pages/InspectionReviewPage.jsx` (referenced in action handlers)
- Action handler: `src/pages/InspectionReviewPage.jsx` (line 686)
- API service: Referenced in frontend code
- Success message: "Inspection returned to Division Chief with remarks."

### Example Use Case
The Legal Unit receives an inspection for legal review but determines that additional information or clarification is needed from the Division Chief before proceeding with legal actions. They return it to the Division Chief with remarks explaining what is needed.

### Workflow Diagram

```text
LEGAL_REVIEW
    ↓ (return_to_division by Legal Unit)
    └─→ DIVISION_REVIEWED
        (Assigned to: Division Chief)
```

---

## Common Return Workflow

All return actions follow a common pattern implemented in `_execute_return_transition()`:

### Common Steps
1. **Validation**: Check user permissions and status validity
2. **Assignee Resolution**: Find appropriate assignee from history or default assignment
3. **Status Transition**: Update inspection status
4. **Assignment**: Assign inspection to target user
5. **History Logging**: Create `InspectionHistory` entry with:
   - Previous status
   - New status
   - Changed by (user who initiated return)
   - Assigned to (target user)
   - Remarks (with return label prefix)
6. **Notification**: Send notification to assignee via `create_return_notification()`
7. **Audit Trail**: Create audit event via `audit_inspection_event()`
8. **Response**: Return updated inspection data

### Common Requirements
- **Remarks**: Most return actions require remarks (except `return_to_previous` and `return_to_division` which have defaults)
- **History Dependency**: Most returns use inspection history to determine appropriate targets and assignees
- **Notification**: All returns trigger notifications to the assignee
- **Audit**: All returns are logged in the audit trail

### Error Handling
All return actions handle:
- Invalid user level (403 Forbidden)
- Invalid status transitions (400 Bad Request)
- Missing assignees (404 Not Found)
- Missing required remarks (400 Bad Request)
- Workflow validation errors (400 Bad Request)

### Code References

**Backend:**
- Main implementation: `server/inspections/views.py`
- Helper method: `_execute_return_transition()` (lines 1948-2020)
- Available actions mapping: `server/inspections/serializers.py` (lines 276-324)

**Frontend:**
- Action handlers: `src/hooks/useInspectionActions.js`
- API services: `src/services/api.js`
- UI components: `src/pages/InspectionReviewPage.jsx`
- Action constants: `src/constants/inspectionConstants.js`

---

## Summary Table

| Action | Who | From Status | To Status | Remarks Required |
|--------|-----|-------------|------------|------------------|
| `return_to_previous` | Monitoring Personnel, Unit Head | `MONITORING_ASSIGNED`, `UNIT_ASSIGNED` | `UNIT_ASSIGNED`, `SECTION_ASSIGNED` | No (auto-generated) |
| `return_to_monitoring` | Unit Head, Section Chief | `MONITORING_COMPLETED_*` | `MONITORING_IN_PROGRESS` | Yes |
| `return_to_unit` | Section Chief | `UNIT_REVIEWED`, `UNIT_COMPLETED_*`, `MONITORING_COMPLETED_*` | `UNIT_IN_PROGRESS`, `MONITORING_IN_PROGRESS` | Yes |
| `return_to_section` | Division Chief | `DIVISION_REVIEWED`, `SECTION_REVIEWED`, `SECTION_COMPLETED_*` | `SECTION_IN_PROGRESS`, `UNIT_REVIEWED/COMPLETED_*`, `MONITORING_IN_PROGRESS` | Yes |
| `return_to_division` | Legal Unit | `LEGAL_REVIEW` | `DIVISION_REVIEWED` | No (has default) |

---

## Notes

- All return actions maintain a complete audit trail for compliance and tracking
- Return actions respect the workflow state machine defined in `Inspection.can_transition_to()`
- Assignee resolution prioritizes history-based assignment over default assignment
- Notifications are sent asynchronously and failures don't block the return action
- Return actions can be used to correct errors, request clarifications, or require rework at any stage

---

*Last Updated: Based on codebase as of current implementation*  
*Documentation Version: 1.0*
