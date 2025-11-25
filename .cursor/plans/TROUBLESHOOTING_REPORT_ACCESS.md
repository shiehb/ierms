# Troubleshooting: "You do not have access to any reports"

## Quick Diagnosis

Run the diagnostic command to check your setup:
```bash
cd server
python manage.py check_report_access
```

For specific user:
```bash
python manage.py check_report_access --user=admin@example.com
```

For specific role:
```bash
python manage.py check_report_access --role="Section Chief"
```

## Common Issues & Solutions

### Issue 1: ReportAccess Table is Empty ❌

**Error in logs:**
```
[REPORT ACCESS] Total entries in ReportAccess table: 0
[REPORT ACCESS] ❌ ReportAccess table is EMPTY!
```

**Cause:** The `reports_reportaccess` table has no data.

**Solution:**

**Option A: Run Management Command**
```bash
cd server
python manage.py seed_report_access
```

**Option B: Run SQL Script**
```bash
# MySQL
mysql -u username -p database_name < seed_report_access.sql

# Or login to MySQL and run:
source /path/to/server/seed_report_access.sql
```

**Verify:**
```sql
SELECT COUNT(*) FROM reports_reportaccess;
-- Should return 42 (total records for all roles)

SELECT role, COUNT(*) as count FROM reports_reportaccess GROUP BY role;
-- Should show counts for each role
```

---

### Issue 2: User Role Doesn't Match Database ⚠️

**Error in logs:**
```
[REPORT ACCESS] User Role: 'SectionChief'
[REPORT ACCESS] Found 0 reports for role 'SectionChief'
[REPORT ACCESS] Expected one of: ['Admin', 'Section Chief', 'Unit Head', ...]
```

**Cause:** User's `userlevel` field doesn't exactly match roles in `ReportAccess` table.

**Common Mismatches:**
- `SectionChief` vs `Section Chief` (missing space)
- `section chief` vs `Section Chief` (wrong case)
- `Admin ` vs `Admin` (extra space)

**Solution:**

**Check user's actual role:**
```sql
SELECT email, userlevel FROM users_user WHERE email = 'your@email.com';
```

**Check roles in ReportAccess:**
```sql
SELECT DISTINCT role FROM reports_reportaccess;
```

**Fix user's role if needed:**
```sql
UPDATE users_user 
SET userlevel = 'Section Chief' 
WHERE email = 'your@email.com';
```

**Or fix via Django Admin:**
1. Login to `/admin`
2. Go to Users
3. Find the user
4. Check "User level" field
5. Make sure it exactly matches one of:
   - `Admin`
   - `Division Chief`
   - `Section Chief`
   - `Unit Head`
   - `Monitoring Personnel`
   - `Legal Unit`

---

### Issue 3: Migration Not Applied 🔧

**Error in logs:**
```
django.db.utils.OperationalError: no such table: reports_reportaccess
```

**Cause:** The `ReportAccess` model migration hasn't been applied.

**Solution:**

**Check migration status:**
```bash
cd server
python manage.py showmigrations reports
```

**If you see unchecked migrations:**
```
reports
  [ ] 0001_initial
  [ ] 0002_reportaccess
```

**Apply migrations:**
```bash
python manage.py migrate reports
```

**If migration doesn't exist, create it:**
```bash
python manage.py makemigrations reports
python manage.py migrate reports
```

---

### Issue 4: Wrong Database Being Used 🗄️

**Symptoms:**
- Data exists in one database
- Application connects to different database
- Logs show empty table but SQL shows data

**Solution:**

**Check Django settings:**
```python
# server/config/settings.py
DATABASES = {
    'default': {
        'NAME': 'your_database_name',  # Check this!
        'USER': 'your_user',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

**Verify connection:**
```bash
cd server
python manage.py dbshell

# Then in database:
SHOW TABLES LIKE '%reportaccess%';
SELECT COUNT(*) FROM reports_reportaccess;
```

---

### Issue 5: User Has No Role Assigned 👤

**Error in logs:**
```
[REPORT ACCESS] User Role: 'None'
[REPORT ACCESS] Found 0 reports for role 'None'
```

**Cause:** User's `userlevel` field is NULL or empty.

**Solution:**

**Check user:**
```sql
SELECT email, userlevel, is_active FROM users_user WHERE email = 'your@email.com';
```

**Assign role:**
```sql
UPDATE users_user 
SET userlevel = 'Section Chief' 
WHERE email = 'your@email.com';
```

---

### Issue 6: Case Sensitivity Problems 🔤

**Error in logs:**
```
[REPORT ACCESS] User Role: 'section chief'
[REPORT ACCESS] Found 0 reports for role 'section chief'
[REPORT ACCESS] Available roles: ['Section Chief', 'Unit Head', ...]
```

**Cause:** Roles in database are case-sensitive. `'section chief'` ≠ `'Section Chief'`

**Solution:**

**Fix user role to match exact case:**
```sql
UPDATE users_user 
SET userlevel = 'Section Chief'  -- Exact case!
WHERE userlevel LIKE 'section%chief';
```

**Verify:**
```sql
SELECT email, userlevel FROM users_user WHERE userlevel = 'Section Chief';
```

---

## Viewing Backend Logs

### Django Development Server
When running `python manage.py runserver`, logs appear in the console:

```
[REPORT ACCESS] User: admin@example.com (ID: 1)
[REPORT ACCESS] User Role: 'Admin' (type: str)
[REPORT ACCESS] Total entries in ReportAccess table: 42
[REPORT ACCESS] Roles found in ReportAccess table: ['Admin', 'Division Chief', ...]
[REPORT ACCESS] Found 13 reports for role 'Admin'
[REPORT ACCESS]   ✓ Billing Report (billing)
[REPORT ACCESS]   ✓ Compliance Report (compliance)
...
[REPORT ACCESS] ✅ Successfully returned 13 reports for admin@example.com
```

### Production Logs
Check your application logs based on deployment:

**Gunicorn/uWSGI:**
```bash
tail -f /var/log/your-app/error.log
```

**Docker:**
```bash
docker logs -f container_name
```

**Systemd:**
```bash
journalctl -u your-app-service -f
```

---

## Debug Response in Frontend

The API now returns debug information when there's an issue:

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

Check browser console (F12) for this information.

---

## Step-by-Step Diagnosis Checklist

### ✅ Step 1: Check if table exists
```sql
SHOW TABLES LIKE '%reportaccess%';
```
Expected: `reports_reportaccess`

### ✅ Step 2: Check if table has data
```sql
SELECT COUNT(*) FROM reports_reportaccess;
```
Expected: 42 rows (or similar)

### ✅ Step 3: Check user's role
```sql
SELECT email, userlevel, is_active FROM users_user WHERE email = 'your@email.com';
```
Expected: Valid role name, is_active = 1

### ✅ Step 4: Check if role exists in ReportAccess
```sql
SELECT COUNT(*) FROM reports_reportaccess WHERE role = 'Your Role';
```
Expected: > 0

### ✅ Step 5: View user's assigned reports
```sql
SELECT r.role, r.report_type, r.display_name 
FROM reports_reportaccess r
JOIN users_user u ON u.userlevel = r.role
WHERE u.email = 'your@email.com'
ORDER BY r.display_name;
```
Expected: List of reports

### ✅ Step 6: Test API endpoint
```bash
# Replace TOKEN with your auth token
curl -H "Authorization: Bearer TOKEN" \
     http://localhost:8000/api/reports/access/
```
Expected: JSON with allowed_reports array

---

## Quick Fixes

### Fix 1: Reset and Reseed Everything
```bash
cd server

# Delete existing data
python manage.py shell
>>> from reports.models import ReportAccess
>>> ReportAccess.objects.all().delete()
>>> exit()

# Reseed
python manage.py seed_report_access

# Verify
python manage.py check_report_access
```

### Fix 2: Standardize User Roles
```sql
-- Update all users to use standard role names
UPDATE users_user SET userlevel = 'Admin' WHERE userlevel LIKE '%admin%';
UPDATE users_user SET userlevel = 'Section Chief' WHERE userlevel LIKE '%section%chief%';
UPDATE users_user SET userlevel = 'Unit Head' WHERE userlevel LIKE '%unit%head%';
UPDATE users_user SET userlevel = 'Monitoring Personnel' WHERE userlevel LIKE '%monitoring%';
UPDATE users_user SET userlevel = 'Division Chief' WHERE userlevel LIKE '%division%';
UPDATE users_user SET userlevel = 'Legal Unit' WHERE userlevel LIKE '%legal%';
```

### Fix 3: Grant Temporary Admin Access
```sql
-- Temporarily give user admin access to test
UPDATE users_user 
SET userlevel = 'Admin' 
WHERE email = 'your@email.com';
```

Then login and check if reports appear. If yes, the issue is role configuration.

---

## Getting Help

If none of the above solutions work, gather this information:

1. **Run diagnostic command:**
```bash
python manage.py check_report_access --user=your@email.com > diagnosis.txt
```

2. **Check backend logs** and copy relevant [REPORT ACCESS] lines

3. **SQL query results:**
```sql
-- User info
SELECT email, userlevel, is_active FROM users_user WHERE email = 'your@email.com';

-- ReportAccess count
SELECT COUNT(*) FROM reports_reportaccess;

-- Roles available
SELECT DISTINCT role FROM reports_reportaccess;
```

4. **API response** from `/api/reports/access/` (check browser Network tab)

5. **Django version and database:**
```bash
python manage.py version
# And check database type/version
```

---

## Prevention Tips

### ✅ Use Consistent Role Names
Always use exact names from the predefined list:
- `Admin`
- `Division Chief`
- `Section Chief`
- `Unit Head`
- `Monitoring Personnel`
- `Legal Unit`

### ✅ Validate on User Creation
Add validation in user forms to only allow valid roles.

### ✅ Regular Checks
Run diagnostic command monthly:
```bash
python manage.py check_report_access
```

### ✅ Document Role Names
Keep a reference document with exact role names for consistency.

---

## Success Indicators

You've fixed the issue when you see:

**In Backend Logs:**
```
[REPORT ACCESS] User: admin@example.com (ID: 1)
[REPORT ACCESS] User Role: 'Admin' (type: str)
[REPORT ACCESS] Total entries in ReportAccess table: 42
[REPORT ACCESS] Found 13 reports for role 'Admin'
[REPORT ACCESS] ✅ Successfully returned 13 reports for admin@example.com
```

**In Frontend:**
- Report dropdown shows available reports
- No error message
- Can select and generate reports

**In API Response:**
```json
{
  "role": "Admin",
  "allowed_reports": [
    {"report_type": "billing", "display_name": "Billing Report"},
    {"report_type": "compliance", "display_name": "Compliance Report"},
    ...
  ]
}
```

✅ **All systems operational!** 🎉

