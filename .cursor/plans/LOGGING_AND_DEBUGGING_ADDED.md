# Logging and Debugging Tools Added

## Overview
Added comprehensive logging and diagnostic tools to help troubleshoot the "You do not have access to any reports" error.

## What Was Added

### 1. Enhanced Logging in `get_report_access()` ✅
**File**: `server/reports/views.py`

**Logs now show:**
- ✅ User email and ID
- ✅ User's role (userlevel)
- ✅ Total entries in ReportAccess table
- ✅ All roles available in database
- ✅ Number of reports found for user's role
- ✅ Each report granted to the user
- ✅ Detailed error messages when no access

**Example log output:**
```
[REPORT ACCESS] User: admin@example.com (ID: 1)
[REPORT ACCESS] User Role: 'Admin' (type: str)
[REPORT ACCESS] Total entries in ReportAccess table: 42
[REPORT ACCESS] Roles found in ReportAccess table: ['Admin', 'Division Chief', 'Section Chief', 'Unit Head', 'Monitoring Personnel', 'Legal Unit']
[REPORT ACCESS] Found 13 reports for role 'Admin'
[REPORT ACCESS]   ✓ Billing Report (billing)
[REPORT ACCESS]   ✓ Compliance Report (compliance)
[REPORT ACCESS]   ✓ Establishment Report (establishment)
[REPORT ACCESS]   ✓ Inspection Report (inspection)
[REPORT ACCESS]   ✓ Law Report (law)
[REPORT ACCESS]   ✓ Monitoring Accomplishment Report (monitoring_accomplishment)
[REPORT ACCESS]   ✓ Non-Compliant Report (non_compliant)
[REPORT ACCESS]   ✓ Notice of Order Report (noo)
[REPORT ACCESS]   ✓ Notice of Violation Report (nov)
[REPORT ACCESS]   ✓ Quota Report (quota)
[REPORT ACCESS]   ✓ Section Accomplishment Report (section_accomplishment)
[REPORT ACCESS]   ✓ Unit Accomplishment Report (unit_accomplishment)
[REPORT ACCESS]   ✓ User Report (user)
[REPORT ACCESS] ✅ Successfully returned 13 reports for admin@example.com
```

**Error scenarios logged:**

**Empty Table:**
```
[REPORT ACCESS] Total entries in ReportAccess table: 0
[REPORT ACCESS] ❌ ReportAccess table is EMPTY! Need to run seed_report_access command or SQL
```

**No Reports for Role:**
```
[REPORT ACCESS] User Role: 'section chief'
[REPORT ACCESS] Found 0 reports for role 'section chief'
[REPORT ACCESS] ⚠️ No reports found for role 'section chief'
[REPORT ACCESS] User role might not match database. Check spelling and case sensitivity.
[REPORT ACCESS] Expected one of: ['Admin', 'Section Chief', 'Unit Head', 'Monitoring Personnel', 'Division Chief', 'Legal Unit']
```

### 2. Enhanced Logging in `generate_report()` ✅
**File**: `server/reports/views.py`

**Logs now show:**
- ✅ User attempting to generate report
- ✅ Report type being requested
- ✅ Access granted or denied
- ✅ User's allowed reports when denied
- ✅ Reason for denial

**Example log output:**
```
[GENERATE REPORT] User: section.chief@example.com attempting to generate 'unit_accomplishment' report
[GENERATE REPORT] User Role: 'Section Chief'
[GENERATE REPORT] ❌ Access DENIED for section.chief@example.com
[GENERATE REPORT] Requested: 'unit_accomplishment' | User's allowed reports: ['billing', 'compliance', 'establishment', 'inspection', 'non_compliant', 'nov', 'noo', 'section_accomplishment']
```

### 3. Debug Information in API Responses ✅
**File**: `server/reports/views.py`

API now returns `debug_info` field when there are issues:

**Empty Table Response:**
```json
{
  "role": "Admin",
  "allowed_reports": [],
  "debug_info": {
    "error": "ReportAccess table is empty",
    "solution": "Run: python manage.py seed_report_access OR execute seed_report_access.sql"
  }
}
```

**No Reports for Role Response:**
```json
{
  "role": "section chief",
  "allowed_reports": [],
  "debug_info": {
    "error": "No reports configured for role: section chief",
    "user_role": "section chief",
    "available_roles": ["Admin", "Section Chief", "Unit Head", "Monitoring Personnel", "Division Chief", "Legal Unit"],
    "suggestion": "Check if user role matches exactly with database entries (case-sensitive)"
  }
}
```

**Access Denied Response:**
```json
{
  "error": "You do not have permission to access this report type",
  "detail": "Report type \"unit_accomplishment\" not allowed for role \"Section Chief\"",
  "debug_info": {
    "requested_report": "unit_accomplishment",
    "user_role": "Section Chief",
    "allowed_reports": ["billing", "compliance", "establishment", "inspection", "non_compliant", "nov", "noo", "section_accomplishment"]
  }
}
```

### 4. Diagnostic Management Command ✅
**File**: `server/reports/management/commands/check_report_access.py`

New command to diagnose access issues:

**Basic usage:**
```bash
python manage.py check_report_access
```

**Output:**
```
======================================================================
  REPORT ACCESS DIAGNOSTIC TOOL
======================================================================

📊 Total ReportAccess entries: 42

📋 Roles configured in ReportAccess:
   • Admin: 13 reports
   • Division Chief: 13 reports
   • Legal Unit: 5 reports
   • Monitoring Personnel: 2 reports
   • Section Chief: 8 reports
   • Unit Head: 6 reports

📈 Summary by Role:

  Admin (13 reports):
    • Billing Report
    • Compliance Report
    • Establishment Report
    ...

  Section Chief (8 reports):
    • Billing Report
    • Compliance Report
    ...

👥 Active Users and Their Roles:

✅ Admin (13 reports):
   • admin@example.com
   • superuser@example.com

✅ Section Chief (8 reports):
   • section.chief@example.com
   • chief2@example.com

💡 Tips:
   • Run with --user=email@example.com to check specific user
   • Run with --role="Section Chief" to check specific role
   • Roles are case-sensitive!
   • If table is empty, run: python manage.py seed_report_access
======================================================================
```

**Check specific user:**
```bash
python manage.py check_report_access --user=admin@example.com
```

**Output:**
```
👤 User Information:
   Email: admin@example.com
   Name: Admin User
   Role (userlevel): "Admin"
   Section: None
   Is Active: True

✅ 13 reports accessible:
   ✓ Billing Report (billing)
   ✓ Compliance Report (compliance)
   ✓ Establishment Report (establishment)
   ...
```

**Check specific role:**
```bash
python manage.py check_report_access --role="Section Chief"
```

**Output:**
```
🔍 Checking role: "Section Chief"

✅ 8 reports configured:
   ✓ Billing Report (billing)
   ✓ Compliance Report (compliance)
   ✓ Establishment Report (establishment)
   ✓ Inspection Report (inspection)
   ✓ Non-Compliant Report (non_compliant)
   ✓ Notice of Order Report (noo)
   ✓ Notice of Violation Report (nov)
   ✓ Section Accomplishment Report (section_accomplishment)
```

### 5. Comprehensive Troubleshooting Guide ✅
**File**: `TROUBLESHOOTING_REPORT_ACCESS.md`

Complete guide covering:
- ✅ Quick diagnosis steps
- ✅ Common issues and solutions
- ✅ Step-by-step checklist
- ✅ SQL queries for debugging
- ✅ How to view logs
- ✅ Quick fixes
- ✅ Prevention tips

## How to Use the Debugging Tools

### Step 1: Check Backend Logs
Start your Django development server:
```bash
cd server
python manage.py runserver
```

Try to access reports in the frontend. Watch the console for `[REPORT ACCESS]` log lines.

### Step 2: Run Diagnostic Command
```bash
python manage.py check_report_access
```

This will show:
- If table is empty
- What roles exist
- What reports each role has
- All users and their roles

### Step 3: Check Specific User
```bash
python manage.py check_report_access --user=your@email.com
```

This will show:
- User's exact role
- Reports they should see
- Any mismatches

### Step 4: Check Frontend Debug Info
Open browser console (F12) and look at the API response from `/api/reports/access/`. It will contain `debug_info` if there's an issue.

### Step 5: Read Troubleshooting Guide
Open `TROUBLESHOOTING_REPORT_ACCESS.md` for detailed solutions to common issues.

## Common Issues You Can Now Debug

### Issue 1: Empty ReportAccess Table
**Before**: Silent failure, no idea why  
**Now**: 
- Logs show: `❌ ReportAccess table is EMPTY!`
- API returns suggestion: `Run: python manage.py seed_report_access`
- Diagnostic command shows: `📊 Total ReportAccess entries: 0`

### Issue 2: Role Mismatch
**Before**: Silent failure, no idea why  
**Now**:
- Logs show: `User Role: 'section chief'`
- Logs show: `Expected one of: ['Section Chief', ...]`
- API returns: Available roles list
- Diagnostic shows exact role spelling needed

### Issue 3: User Has Wrong Role
**Before**: Hard to identify which role user has  
**Now**:
- Logs show: Exact user role with type
- Diagnostic shows: User info including role
- Can compare user's role vs database roles

### Issue 4: Permission Denied on Generation
**Before**: Just "403 Forbidden"  
**Now**:
- Logs show: What report was requested
- Logs show: What reports user CAN access
- API returns: List of allowed reports in debug_info

## Files Modified

1. ✅ `server/reports/views.py`
   - Added comprehensive logging to `get_report_access()`
   - Added detailed logging to `generate_report()`
   - Added `debug_info` in API responses

2. ✅ `server/reports/management/commands/check_report_access.py` (NEW)
   - Diagnostic command for checking access configuration
   - Supports `--user` and `--role` flags
   - Shows summary, users, and recommendations

3. ✅ `TROUBLESHOOTING_REPORT_ACCESS.md` (NEW)
   - Complete troubleshooting guide
   - Common issues and solutions
   - Step-by-step diagnosis
   - SQL queries and quick fixes

4. ✅ `LOGGING_AND_DEBUGGING_ADDED.md` (this file)
   - Summary of what was added
   - How to use the tools
   - Examples and benefits

## Benefits

### For Developers
- ✅ Instant visibility into permission issues
- ✅ Clear error messages in logs
- ✅ Easy to identify configuration problems
- ✅ Diagnostic command for quick checks

### For System Administrators
- ✅ Can diagnose user issues without code knowledge
- ✅ Clear steps to fix common problems
- ✅ Can check any user's access quickly
- ✅ Troubleshooting guide for reference

### For Support Teams
- ✅ Debug info in API responses
- ✅ Can ask users to check browser console
- ✅ Clear instructions to provide to users
- ✅ Fast identification of root cause

## Next Steps

1. **Restart Django Server** to see the new logs:
```bash
cd server
python manage.py runserver
```

2. **Run Diagnostic Command**:
```bash
python manage.py check_report_access
```

3. **Try Accessing Reports** and watch the logs

4. **If Issues Found**, follow the troubleshooting guide

5. **Seed Data** if table is empty:
```bash
python manage.py seed_report_access
```

## Example Debugging Session

```bash
# Step 1: Run diagnostic
$ python manage.py check_report_access --user=user@example.com

👤 User Information:
   Email: user@example.com
   Role (userlevel): "section chief"
   
❌ No reports found for role: "section chief"
   Possible issues:
   • Role spelling mismatch (check case sensitivity)
   • Expected one of: Admin, Section Chief, Unit Head, ...

# Issue identified: Role should be "Section Chief" not "section chief"

# Step 2: Fix the user's role
$ python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> user = User.objects.get(email='user@example.com')
>>> user.userlevel = 'Section Chief'
>>> user.save()
>>> exit()

# Step 3: Verify
$ python manage.py check_report_access --user=user@example.com

👤 User Information:
   Email: user@example.com
   Role (userlevel): "Section Chief"
   
✅ 8 reports accessible:
   ✓ Billing Report (billing)
   ✓ Compliance Report (compliance)
   ...

# Fixed! ✅
```

## Summary

🎉 **You now have powerful debugging tools to diagnose and fix report access issues!**

- ✅ Detailed logs show exactly what's happening
- ✅ Diagnostic command identifies configuration problems
- ✅ Debug info in API helps frontend debugging
- ✅ Comprehensive troubleshooting guide available
- ✅ Easy to identify and fix common issues

**No more silent failures!** Every access check is now logged and debuggable. 🔍✨

