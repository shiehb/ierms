# 🔧 Manual Fix: Insert ReportAccess Data

## The Problem
The management command isn't outputting results. Let's insert the data directly into the database.

## ✅ Solution: Run SQL Directly

### Option 1: Using phpMyAdmin or MySQL Workbench

1. **Open your database tool** (phpMyAdmin, MySQL Workbench, etc.)

2. **Select your database**

3. **Open the SQL tab**

4. **Copy and paste** the entire contents of `INSERT_REPORT_ACCESS.sql`

5. **Click "Execute" or "Go"**

6. **You should see**: "42 rows affected"

### Option 2: Using MySQL Command Line

```bash
# Login to MySQL
mysql -u your_username -p your_database_name

# Then paste the contents of INSERT_REPORT_ACCESS.sql
# Or run the file directly:
source C:\Users\ming\Documents\GitHub\integrated_establishments_regulatory_management_system\INSERT_REPORT_ACCESS.sql
```

### Option 3: Using Django Shell

```bash
cd server
..\venv\Scripts\python.exe manage.py shell
```

Then paste this:

```python
from reports.models import ReportAccess

# Clear existing
ReportAccess.objects.all().delete()

# Define all mappings
mappings = [
    # Monitoring Personnel
    ("Monitoring Personnel", "inspection", "Inspection Report"),
    ("Monitoring Personnel", "monitoring_accomplishment", "Monitoring Accomplishment Report"),
    
    # Unit Head
    ("Unit Head", "inspection", "Inspection Report"),
    ("Unit Head", "compliance", "Compliance Report"),
    ("Unit Head", "non_compliant", "Non-Compliant Report"),
    ("Unit Head", "unit_accomplishment", "Unit Accomplishment Report"),
    ("Unit Head", "nov", "Notice of Violation Report"),
    ("Unit Head", "noo", "Notice of Order Report"),
    
    # Section Chief
    ("Section Chief", "inspection", "Inspection Report"),
    ("Section Chief", "compliance", "Compliance Report"),
    ("Section Chief", "non_compliant", "Non-Compliant Report"),
    ("Section Chief", "billing", "Billing Report"),
    ("Section Chief", "establishment", "Establishment Report"),
    ("Section Chief", "section_accomplishment", "Section Accomplishment Report"),
    ("Section Chief", "nov", "Notice of Violation Report"),
    ("Section Chief", "noo", "Notice of Order Report"),
    
    # Division Chief
    ("Division Chief", "user", "User Report"),
    ("Division Chief", "establishment", "Establishment Report"),
    ("Division Chief", "law", "Law Report"),
    ("Division Chief", "quota", "Quota Report"),
    ("Division Chief", "billing", "Billing Report"),
    ("Division Chief", "compliance", "Compliance Report"),
    ("Division Chief", "non_compliant", "Non-Compliant Report"),
    ("Division Chief", "inspection", "Inspection Report"),
    ("Division Chief", "section_accomplishment", "Section Accomplishment Report"),
    ("Division Chief", "unit_accomplishment", "Unit Accomplishment Report"),
    ("Division Chief", "monitoring_accomplishment", "Monitoring Accomplishment Report"),
    ("Division Chief", "nov", "Notice of Violation Report"),
    ("Division Chief", "noo", "Notice of Order Report"),
    
    # Legal Unit
    ("Legal Unit", "billing", "Billing Report"),
    ("Legal Unit", "non_compliant", "Non-Compliant Report"),
    ("Legal Unit", "compliance", "Compliance Report"),
    ("Legal Unit", "nov", "Notice of Violation Report"),
    ("Legal Unit", "noo", "Notice of Order Report"),
    
    # Admin
    ("Admin", "user", "User Report"),
    ("Admin", "establishment", "Establishment Report"),
    ("Admin", "law", "Law Report"),
    ("Admin", "quota", "Quota Report"),
    ("Admin", "billing", "Billing Report"),
    ("Admin", "compliance", "Compliance Report"),
    ("Admin", "non_compliant", "Non-Compliant Report"),
    ("Admin", "inspection", "Inspection Report"),
    ("Admin", "section_accomplishment", "Section Accomplishment Report"),
    ("Admin", "unit_accomplishment", "Unit Accomplishment Report"),
    ("Admin", "monitoring_accomplishment", "Monitoring Accomplishment Report"),
    ("Admin", "nov", "Notice of Violation Report"),
    ("Admin", "noo", "Notice of Order Report"),
]

# Insert all
for role, report_type, display_name in mappings:
    ReportAccess.objects.create(
        role=role,
        report_type=report_type,
        display_name=display_name
    )
    print(f"✓ {role} -> {display_name}")

print(f"\n✅ Created {ReportAccess.objects.count()} entries")
```

## ✅ Verify It Worked

After inserting, run this query:

```sql
SELECT role, COUNT(*) as count 
FROM reports_reportaccess 
GROUP BY role;
```

**Expected results:**
```
Admin                  | 13
Division Chief         | 13
Legal Unit            | 5
Monitoring Personnel  | 2
Section Chief         | 8
Unit Head             | 6
```

## 🔄 After Data Is Inserted

1. **Refresh your browser** (Ctrl + F5)
2. **Go to Reports page**
3. **Check your console logs** - should now show:
   ```
   [REPORT ACCESS] Total entries in ReportAccess table: 42
   [REPORT ACCESS] Found X reports for role 'Your Role'
   ```
4. **Reports dropdown should show your available reports**

## 🔍 Check Your User's Role

While you're in the database, also check your user's role:

```sql
SELECT email, userlevel, is_active 
FROM users_user 
WHERE email = 'your@email.com';
```

**Important**: The `userlevel` must EXACTLY match one of these (case-sensitive!):
- `Admin`
- `Division Chief`
- `Section Chief`
- `Unit Head`
- `Monitoring Personnel`
- `Legal Unit`

If it doesn't match exactly, fix it:

```sql
UPDATE users_user 
SET userlevel = 'Admin'  -- or whichever role is correct
WHERE email = 'your@email.com';
```

## 🎯 Quick Test

After inserting data, test the API:

1. Open browser console (F12)
2. Go to Network tab
3. Navigate to `/reports` page
4. Find the request to `/api/reports/access/`
5. Check the response - should show your allowed reports

## Still Not Working?

If you still see "No access to any reports" after inserting data:

1. **Check user's role matches database** (see above)
2. **Clear browser cache** completely
3. **Restart Django server**
4. **Check console logs** for the detailed [REPORT ACCESS] messages
5. **Share the logs** - they will tell us exactly what's wrong

---

**Files to use:**
- `INSERT_REPORT_ACCESS.sql` - The SQL script to run
- This file - Instructions on how to run it

Choose whichever method you're most comfortable with! 🚀

