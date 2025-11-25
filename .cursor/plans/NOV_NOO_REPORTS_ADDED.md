# Notice of Violation (NOV) and Notice of Order (NOO) Reports Added

## Overview
Successfully added two new report types to the centralized report dashboard:
1. **Notice of Violation (NOV) Report** - Track and report on violations issued to establishments
2. **Notice of Order (NOO) Report** - Track and report on penalty orders issued to establishments

## Changes Made

### 1. Backend Report Generators ✅
**File**: `server/reports/generators.py`

#### Added Imports
```python
from inspections.models import Inspection, BillingRecord, ComplianceQuota, NoticeOfViolation, NoticeOfOrder
```

#### NoticeOfViolationReportGenerator
- **Report Type**: `nov`
- **Report Title**: "Notice of Violation Report"
- **Columns**:
  - Inspection Code
  - Establishment
  - Law
  - Date Sent
  - Compliance Deadline
  - Violations
  - Recipient
  - Sent By
  - Status (Overdue, Due Today, Pending, No Deadline)

- **Filters Supported**:
  - Date range (by sent_date)
  - Law
  - Establishment ID
  - Sent by user ID
  - Status (PENDING/OVERDUE)

- **Key Features**:
  - Shows NOVs with related inspection and establishment data
  - Truncates long violation text to 100 characters
  - Calculates status based on compliance deadline
  - Orders by most recent sent date

#### NoticeOfOrderReportGenerator
- **Report Type**: `noo`
- **Report Title**: "Notice of Order Report"
- **Columns**:
  - Inspection Code
  - Establishment
  - Law
  - Date Sent
  - Penalty Fees (formatted as ₱X,XXX.XX)
  - Payment Deadline
  - Recipient
  - Sent By
  - Status (Overdue, Due Today, Pending, No Deadline)

- **Filters Supported**:
  - Date range (by sent_date)
  - Law
  - Establishment ID
  - Sent by user ID
  - Status (PENDING/OVERDUE)
  - Min/Max penalty amount

- **Key Features**:
  - Shows NOOs with related inspection and establishment data
  - Formats penalty fees with Philippine Peso symbol
  - Calculates payment status based on deadline
  - Orders by most recent sent date

### 2. API Endpoints Updated ✅
**File**: `server/reports/views.py`

#### Updated `get_report_access()`
Added new report types to the hardcoded list for temporary access control bypass:
```python
{'report_type': 'nov', 'display_name': 'Notice of Violation Report'},
{'report_type': 'noo', 'display_name': 'Notice of Order Report'},
```

#### Updated `get_filter_options()`
Added filter options for NOV and NOO reports:
- **Laws**: Active laws with reference codes and titles
- **Establishments**: Active establishments
- **Senders**: Active users who can send NOV/NOO
- **Status Options**:
  - All
  - Pending (deadline in future)
  - Overdue (deadline passed)

### 3. Access Control Configuration ✅
**Files**: 
- `server/seed_report_access.sql`
- `server/reports/management/commands/seed_report_access.py`

Updated role-based access for NOV and NOO reports:

| Role | Access to NOV/NOO |
|------|-------------------|
| Monitoring Personnel | ❌ No access |
| Unit Head | ✅ Full access |
| Section Chief | ✅ Full access |
| Division Chief | ✅ Full access |
| Legal Unit | ✅ Full access |
| Admin | ✅ Full access |

**Rationale**: 
- Legal Unit needs access to track violations and orders
- Unit Heads and above need visibility for oversight
- Monitoring Personnel focus on inspections, not legal actions

### 4. Report Registry Updated ✅
**File**: `server/reports/generators.py`

Added to the `REPORT_GENERATORS` dictionary:
```python
'nov': NoticeOfViolationReportGenerator,
'noo': NoticeOfOrderReportGenerator,
```

## Database Models Referenced

### NoticeOfViolation Model
- Linked to `InspectionForm` (which links to `Inspection`)
- Fields used in report:
  - `sent_date` - When NOV was sent
  - `compliance_deadline` - Deadline for compliance
  - `violations` - Text description of violations
  - `recipient_name` - Who received the NOV
  - `sent_by` - User who sent the NOV
  - Related: `inspection_form.inspection` (code, law, establishments)

### NoticeOfOrder Model
- Linked to `InspectionForm` (which links to `Inspection`)
- Fields used in report:
  - `sent_date` - When NOO was sent
  - `penalty_fees` - Amount of penalty
  - `payment_deadline` - Deadline for payment
  - `recipient_name` - Who received the NOO
  - `sent_by` - User who sent the NOO
  - Related: `inspection_form.inspection` (code, law, establishments)

## Frontend Integration

The reports will automatically appear in the Reports dropdown on the frontend because:
1. They're added to the `get_report_access()` response
2. Filter options are provided by `get_filter_options()`
3. The report generation flow uses the dispatcher pattern

**No frontend code changes needed!** The dynamic report system handles:
- Report type selection
- Filter rendering
- Time period selection
- Report generation
- Table display with pagination

## Testing the New Reports

### 1. Access the Reports Page
Navigate to `/reports` in the application

### 2. Select Report Type
Choose either:
- "Notice of Violation Report" 
- "Notice of Order Report"
from the dropdown

### 3. Configure Filters
- **Time Period**: Quarterly, Monthly, or Custom date range
- **Law**: Filter by specific law (optional)
- **Establishment**: Filter by specific establishment (optional)
- **Sender**: Filter by who sent the NOV/NOO (optional)
- **Status**: Filter by Pending or Overdue (optional)
- **For NOO Only**: Min/Max penalty amount filters

### 4. Generate Report
Click "Generate Report" to see results

### 5. Export Data
Use "Export CSV" to download the report data

## Status Calculation Logic

### Notice of Violation Status
```
if compliance_deadline exists:
    if deadline < today:
        status = "Overdue"
    elif deadline == today:
        status = "Due Today"
    else:
        status = "Pending"
else:
    status = "No Deadline"
```

### Notice of Order Status
```
if payment_deadline exists:
    if deadline < today:
        status = "Overdue"
    elif deadline == today:
        status = "Due Today"
    else:
        status = "Pending"
else:
    status = "No Deadline"
```

## Sample Report Output

### NOV Report Sample
| Inspection Code | Establishment | Law | Date Sent | Compliance Deadline | Violations | Recipient | Sent By | Status |
|-----------------|---------------|-----|-----------|---------------------|------------|-----------|---------|---------|
| INS-2025-001 | ABC Corp | RA 8749 | 2025-01-15 | 2025-02-15 10:00 | Non-compliance with air quality standards... | John Doe | Admin User | Pending |
| INS-2025-002 | XYZ Inc | PD 1586 | 2025-01-10 | 2025-01-20 14:00 | Environmental clearance expired... | Jane Smith | Legal Officer | Due Today |

### NOO Report Sample
| Inspection Code | Establishment | Law | Date Sent | Penalty Fees | Payment Deadline | Recipient | Sent By | Status |
|-----------------|---------------|-----|-----------|--------------|------------------|-----------|---------|---------|
| INS-2025-003 | DEF Ltd | RA 9003 | 2025-01-05 | ₱50,000.00 | 2025-02-05 | Bob Johnson | Legal Head | Pending |
| INS-2025-004 | GHI Co | PD 984 | 2024-12-15 | ₱25,000.00 | 2025-01-15 | Alice Wong | Admin | Overdue |

## Benefits

1. **Centralized Tracking**: All NOVs and NOOs in one place
2. **Status Monitoring**: Quickly identify overdue compliance/payments
3. **Law-based Analysis**: Filter by specific environmental laws
4. **Accountability**: Track who sent each notice
5. **Deadline Management**: See upcoming and overdue deadlines
6. **Financial Overview**: Track penalty amounts (NOO report)
7. **Export Capability**: Download data for further analysis

## Future Enhancements

Potential improvements for these reports:
1. Add compliance status tracking (did they comply?)
2. Include follow-up action dates
3. Link to payment records for NOOs
4. Add violation severity classification
5. Include repeat offender indicators
6. Add graphical dashboard for trends
7. Email notification integration
8. Automatic escalation for overdue items

## Bug Fixes

### Fixed User Model Method Error
**Issue**: Initial implementation used `get_full_name()` which doesn't exist on the User model  
**Error**: `AttributeError: 'User' object has no attribute 'get_full_name'`  
**Solution**: Added `_format_user()` helper method to both NOV and NOO generators that properly formats user names:
```python
def _format_user(self, user):
    """Format user display name"""
    if not user:
        return 'N/A'
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}"
    return user.email
```

This matches the pattern used in other report generators throughout the system.

## Files Modified Summary

1. ✅ `server/reports/generators.py` - Added 2 new generator classes (with user formatting fix)
2. ✅ `server/reports/views.py` - Updated access list and filter options
3. ✅ `server/seed_report_access.sql` - Added access mappings
4. ✅ `server/reports/management/commands/seed_report_access.py` - Updated default access

## Next Steps

1. **Test the Reports**: Generate sample NOV and NOO reports to verify functionality
2. **Seed Access Data**: Run the management command or SQL script to set up access control
3. **User Training**: Inform users about the new report types
4. **Monitor Usage**: Track which roles use these reports most frequently
5. **Gather Feedback**: Ask users if additional filters or columns are needed

## Documentation
- All code includes inline comments for maintainability
- Generator classes follow the established BaseReportGenerator pattern
- Consistent naming conventions throughout
- Error handling included in API endpoints

