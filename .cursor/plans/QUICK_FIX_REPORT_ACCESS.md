# Quick Fix: Report Access Issue

## Problem
You're seeing "You do not have access to any reports" because the `reports_reportaccess` table is empty.

## Solution Options

### Option 1: Run SQL Directly (RECOMMENDED - FASTEST)

1. **Open your MySQL client** (phpMyAdmin, MySQL Workbench, or command line)

2. **Select your database**: `db_ierms` (or your database name)

3. **Run this SQL**:
   ```sql
   -- Run the SQL file
   SOURCE C:/Users/ming/Documents/GitHub/integrated_establishments_regulatory_management_system/server/seed_report_access.sql;
   ```

   OR copy-paste the SQL from `server/seed_report_access.sql`

4. **Verify**: You should see 30 records inserted

5. **Refresh your browser** at `http://localhost:5173/reports`

---

### Option 2: Run Python Script

1. **Open Command Prompt** in the project root directory

2. **Run**:
   ```bash
   venv\Scripts\python.exe server\seed_data.py
   ```

3. **Refresh your browser**

---

### Option 3: Django Admin (If you have admin access)

1. **Go to**: `http://127.0.0.1:8000/admin/`

2. **Login** with your admin credentials

3. **Go to**: Reports → Report Access

4. **Manually add records**:
   - For your user role (e.g., "Admin" or "Division Chief")
   - Add report types: inspection, establishment, user, law, quota, billing, compliance, non_compliant

---

### Option 4: Use Django Shell

1. **Open Command Prompt** in the server directory

2. **Run**:
   ```bash
   ..\venv\Scripts\python.exe manage.py shell
   ```

3. **Copy-paste this code**:
   ```python
   from reports.models import ReportAccess
   
   # Clear existing
   ReportAccess.objects.all().delete()
   
   # Create records
   mappings = [
       ("Admin", "user"), ("Admin", "establishment"), ("Admin", "law"),
       ("Admin", "quota"), ("Admin", "billing"), ("Admin", "compliance"),
       ("Admin", "non_compliant"), ("Admin", "inspection"),
       
       ("Division Chief", "user"), ("Division Chief", "establishment"),
       ("Division Chief", "law"), ("Division Chief", "quota"),
       ("Division Chief", "billing"), ("Division Chief", "compliance"),
       ("Division Chief", "non_compliant"), ("Division Chief", "inspection"),
       
       ("Section Chief", "inspection"), ("Section Chief", "compliance"),
       ("Section Chief", "non_compliant"), ("Section Chief", "billing"),
       ("Section Chief", "establishment"),
       
       ("Unit Head", "inspection"), ("Unit Head", "compliance"),
       ("Unit Head", "non_compliant"),
       
       ("Monitoring Personnel", "inspection"),
       
       ("Legal Unit", "billing"), ("Legal Unit", "non_compliant"),
       ("Legal Unit", "compliance"),
   ]
   
   for role, report_type in mappings:
       ReportAccess.objects.create(role=role, report_type=report_type)
   
   print(f"Created {ReportAccess.objects.count()} records")
   exit()
   ```

4. **Refresh your browser**

---

## Verify It Worked

### Check in Browser
1. Go to `http://localhost:5173/reports`
2. You should now see a dropdown with report types

### Check in Database
Run this SQL:
```sql
SELECT * FROM reports_reportaccess ORDER BY role, report_type;
```

You should see 30 records (or more if you added extras).

### Check via API
Open browser and go to:
```
http://127.0.0.1:8000/api/reports/access/
```

You should see JSON with your role and allowed reports.

---

## What Reports Each Role Gets

| Role | Number of Reports | Report Types |
|------|-------------------|--------------|
| **Admin** | 8 (All) | User, Establishment, Law, Quota, Billing, Compliance, Non-Compliant, Inspection |
| **Division Chief** | 8 (All) | User, Establishment, Law, Quota, Billing, Compliance, Non-Compliant, Inspection |
| **Section Chief** | 5 | Inspection, Compliance, Non-Compliant, Billing, Establishment |
| **Unit Head** | 3 | Inspection, Compliance, Non-Compliant |
| **Monitoring Personnel** | 1 | Inspection |
| **Legal Unit** | 3 | Billing, Non-Compliant, Compliance |

---

## Still Not Working?

### Debug Steps

1. **Check your user role**:
   ```sql
   SELECT email, userlevel FROM users_user WHERE email = 'your-email@example.com';
   ```

2. **Check what's in ReportAccess**:
   ```sql
   SELECT * FROM reports_reportaccess WHERE role = 'YOUR_ROLE';
   ```
   (Replace YOUR_ROLE with your actual role, e.g., 'Admin')

3. **Check the role matches exactly**:
   - The role in `users_user.userlevel` must EXACTLY match `reports_reportaccess.role`
   - Check for spaces, capitalization, etc.

4. **Test the API directly**:
   - Open: `http://127.0.0.1:8000/api/reports/access/`
   - Check the JSON response
   - Look for `"allowed_reports": []` (empty means no matches found)

---

## Contact for Help

If none of these work, provide:
1. Your user role (from database)
2. Output of: `SELECT COUNT(*) FROM reports_reportaccess;`
3. Any error messages in browser console (F12 → Console tab)

