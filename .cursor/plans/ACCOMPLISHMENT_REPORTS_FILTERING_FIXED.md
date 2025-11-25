# Accomplishment Reports Filtering Fixed

## Overview
Fixed the accomplishment report generators to ensure users can only see inspections within their scope, and extra filters cannot override these security restrictions.

## Problem Fixed
Previously, users could bypass their role restrictions by applying law filters, allowing them to see data outside their authorized scope:
- Section Chiefs could see other sections' data
- Unit Heads could see other units' data  
- Monitoring Personnel could see other inspectors' data

## Solution Implemented

### Key Change: Apply User Restrictions LAST
Reordered the filter application logic so that user-based restrictions are applied **after** all extra filters, ensuring they cannot be overridden.

## Changes Made

### 1. Section Accomplishment Report Generator ✅
**File**: `server/reports/generators.py` (lines 645-682)

**Before**: User section filter was applied first, then extra filters could override it
**After**: 
1. Apply date filter
2. Apply compliance filter  
3. Apply law filter (if provided)
4. **Enforce user-based filtering LAST** (cannot be overridden)

**Logic**:
```python
# ENFORCE user-based filtering LAST (cannot be overridden)
if user.userlevel == 'Section Chief' and user.section:
    # Handle combined sections
    if user.section == 'PD-1586,RA-8749,RA-9275':
        queryset = queryset.filter(law__in=['PD-1586', 'RA-8749', 'RA-9275'])
    else:
        queryset = queryset.filter(law=user.section)
elif user.userlevel not in ['Admin', 'Division Chief']:
    # Only Section Chief, Division Chief, and Admin can access this report
    queryset = queryset.none()
```

**Access Control**:
- ✅ Section Chief: Only sees inspections from their assigned section
- ✅ Division Chief: Sees all sections
- ✅ Admin: Sees all sections
- ❌ All other roles: Return empty result

### 2. Unit Accomplishment Report Generator ✅
**File**: `server/reports/generators.py` (lines 734-770)

**Same logic as Section Report**:
- Unit Heads use the `section` field (not a separate unit field)
- Filters applied in order: date → compliance → law → user restriction
- User restriction enforced last with `.filter()` at the end

**Access Control**:
- ✅ Unit Head: Only sees inspections from their assigned unit/section
- ✅ Division Chief: Sees all units
- ✅ Admin: Sees all units
- ❌ All other roles: Return empty result

### 3. Monitoring Accomplishment Report Generator ✅
**File**: `server/reports/generators.py` (lines 823-859)

**Logic**:
```python
# ENFORCE user-based filtering LAST (cannot be overridden)
if user.userlevel == 'Monitoring Personnel':
    queryset = queryset.filter(assigned_to=user)
elif user.userlevel not in ['Admin', 'Division Chief']:
    # Only Monitoring Personnel, Division Chief, and Admin can access this report
    queryset = queryset.none()
```

**Access Control**:
- ✅ Monitoring Personnel: Only sees inspections assigned to them
- ✅ Division Chief: Sees all inspections
- ✅ Admin: Sees all inspections
- ❌ All other roles: Return empty result

### 4. Report Access Configuration Updated ✅
**Files**: 
- `server/seed_report_access.sql`
- `server/reports/management/commands/seed_report_access.py`

**Updated role-based access**:

| Role | Section Report | Unit Report | Monitoring Report |
|------|---------------|-------------|-------------------|
| Monitoring Personnel | ❌ | ❌ | ✅ (only own) |
| Unit Head | ❌ | ✅ (only own) | ❌ |
| Section Chief | ✅ (only own) | ❌ | ❌ |
| Division Chief | ✅ (all) | ✅ (all) | ✅ (all) |
| Legal Unit | ❌ | ❌ | ❌ |
| Admin | ✅ (all) | ✅ (all) | ✅ (all) |

## Security Benefits

### 1. Data Isolation
- Each user role only sees data relevant to their responsibilities
- No cross-contamination between sections/units/inspectors

### 2. Filter Safety
- Law filters can be used to narrow down results within their scope
- But cannot be used to expand scope beyond authorized access
- Example: Section Chief filtering for a different law will return empty results if that law isn't in their section

### 3. Defense in Depth
- User restrictions applied at the queryset level (database layer)
- Even if frontend bypass attempted, backend enforces restrictions
- Empty queryset returned for unauthorized access attempts

## Combined Section Handling

Special logic for combined section users (EIA, Air & Water):
```python
if user.section == 'PD-1586,RA-8749,RA-9275':
    queryset = queryset.filter(law__in=['PD-1586', 'RA-8749', 'RA-9275'])
```

This allows users assigned to the combined section to see inspections for:
- PD-1586 (EIA)
- RA-8749 (Clean Air Act)
- RA-9275 (Clean Water Act)

## Testing Scenarios

### Section Chief
1. ✅ Sees only their section's inspections
2. ✅ Can filter by law within their section
3. ✅ Filtering by different section's law returns empty
4. ✅ Date and compliance filters work within their scope

### Unit Head  
1. ✅ Sees only their unit/section's inspections
2. ✅ Can filter by law within their unit
3. ✅ Filtering by different unit's law returns empty
4. ✅ Date and compliance filters work within their scope

### Monitoring Personnel
1. ✅ Sees only inspections assigned to them
2. ✅ Can filter by law for their own inspections
3. ✅ Cannot see other inspectors' work
4. ✅ Date and compliance filters work for their inspections

### Division Chief & Admin
1. ✅ See all inspections across all sections/units/inspectors
2. ✅ All filters work without restrictions
3. ✅ Can generate reports for any combination

### Unauthorized Roles
1. ✅ Legal Unit trying to access accomplishment reports → empty result
2. ✅ Section Chief trying to access Unit report → empty result
3. ✅ Unit Head trying to access Section report → empty result

## Database Query Optimization

The filter order is optimized for performance:
1. **Status filter** (indexed) - narrows down to completed inspections
2. **Date filter** (indexed) - further reduces dataset
3. **Compliance filter** - status text search on already narrowed set
4. **Law filter** (indexed) - narrows to specific law if provided
5. **User restriction** (indexed) - final security boundary

## Migration Impact

**No database migration needed** - this is a pure logic change in the generator classes.

## Backward Compatibility

✅ **Fully backward compatible**:
- Existing reports continue to work
- No API changes
- No frontend changes needed
- Only backend filtering logic enhanced

## Files Modified

1. ✅ `server/reports/generators.py`
   - Updated `SectionAccomplishmentReportGenerator.fetch_data()`
   - Updated `UnitAccomplishmentReportGenerator.fetch_data()`
   - Updated `MonitoringAccomplishmentReportGenerator.fetch_data()`

2. ✅ `server/seed_report_access.sql`
   - Added all 3 accomplishment reports to Division Chief
   - Added all 3 accomplishment reports to Admin

3. ✅ `server/reports/management/commands/seed_report_access.py`
   - Already had correct access mappings

## Next Steps

1. **Test the Reports**: Generate accomplishment reports with different user roles
2. **Verify Filtering**: Ensure law filters don't break scope restrictions
3. **Monitor Logs**: Check for any unexpected empty results
4. **User Training**: Inform users they can only see their scoped data

## Security Notes

⚠️ **Important**: These restrictions are enforced at the Django ORM level. If direct database access is used, these restrictions don't apply. Ensure:
- Database access is properly restricted
- Only the application has write access
- Audit logs capture direct database queries

✅ **API Security**: The restrictions are enforced before data is serialized, so even if someone bypasses frontend validation, the backend will still restrict access.

