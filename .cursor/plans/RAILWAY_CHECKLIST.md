# Railway Deployment Checklist

Use this checklist to track your deployment progress. Check off each item as you complete it.

## Pre-Deployment Setup
- [ ] All code is committed to GitHub
- [ ] Railway account created
- [ ] GitHub account connected to Railway

## Project Setup
- [ ] New Railway project created
- [ ] GitHub repository connected
- [ ] Initial deployment started

## Database Setup
- [ ] MySQL database service added
- [ ] MySQL connection details copied:
  - [ ] MYSQLDATABASE
  - [ ] MYSQLUSER
  - [ ] MYSQLPASSWORD
  - [ ] MYSQLHOST
  - [ ] MYSQLPORT

## Redis Setup
- [ ] Redis service added
- [ ] REDIS_URL copied

## Environment Variables
- [ ] DJANGO_SECRET_KEY set (use: `3X-SwnFsco_KWzpph-gBpuLiRnfbnzsY69cWm3xodekbxPVXQdHrLUlsg9woRDjg3Ho`)
- [ ] DEBUG set to `False`
- [ ] ALLOWED_HOSTS set to `*.railway.app`
- [ ] DB_NAME set
- [ ] DB_USER set
- [ ] DB_PASSWORD set
- [ ] DB_HOST set
- [ ] DB_PORT set
- [ ] CELERY_BROKER_URL set
- [ ] CELERY_RESULT_BACKEND set
- [ ] CORS_ALLOW_ALL_ORIGINS set to `False`
- [ ] FRONTEND_URL set (optional)

## Deployment
- [ ] Build completed successfully
- [ ] No errors in deployment logs

## Database Setup
- [ ] Migrations run successfully
- [ ] Superuser account created
- [ ] Static files collected

## Testing
- [ ] Backend URL accessible
- [ ] Admin panel accessible
- [ ] Can login with superuser
- [ ] API endpoints working

## Frontend Integration
- [ ] Frontend API URL updated
- [ ] Frontend redeployed (if needed)
- [ ] CORS configured correctly

## Optional
- [ ] Custom domain configured
- [ ] Celery worker service added
- [ ] Monitoring set up

---

## Your Generated Secret Key

**DJANGO_SECRET_KEY**: 
```
3X-SwnFsco_KWzpph-gBpuLiRnfbnzsY69cWm3xodekbxPVXQdHrLUlsg9woRDjg3Ho
```

**⚠️ Important**: Keep this secret key safe! Don't share it publicly.

---

## Quick Reference

### Your Railway Project URL
(Add after Step 12): `https://________________.railway.app`

### Your MySQL Connection Details
- Database: `________________`
- User: `________________`
- Password: `________________`
- Host: `________________`
- Port: `________________`

### Your Redis URL
- URL: `________________`

---

## Common Commands

### Run Migrations
```bash
cd server && python manage.py migrate
```

### Create Superuser
```bash
cd server && python manage.py createsuperuser
```

### Collect Static Files
```bash
cd server && python manage.py collectstatic --noinput
```

---

**Status**: Ready to deploy! 🚀

