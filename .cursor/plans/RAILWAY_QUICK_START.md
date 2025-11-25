# Railway Quick Start Guide

This is a simplified guide to deploy your Django app on Railway in under 10 minutes.

## Step 1: Sign Up
1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub (recommended)

## Step 2: Create Project
1. Click **"New Project"**
2. Select **"Deploy from GitHub repo"**
3. Choose your repository: `integrated_establishments_regulatory_management_system`

## Step 3: Add MySQL Database
1. In your project, click **"New"** → **"Database"** → **"Add MySQL"**
2. Railway will create a MySQL database automatically
3. Click on the database service
4. Go to **"Variables"** tab
5. Copy these values (you'll need them):
   - `MYSQLDATABASE` → Use as `DB_NAME`
   - `MYSQLUSER` → Use as `DB_USER`
   - `MYSQLPASSWORD` → Use as `DB_PASSWORD`
   - `MYSQLHOST` → Use as `DB_HOST`
   - `MYSQLPORT` → Use as `DB_PORT`

## Step 4: Add Redis (for Celery)
1. Click **"New"** → **"Database"** → **"Add Redis"**
2. Click on the Redis service
3. Go to **"Variables"** tab
4. Copy `REDIS_URL` (you'll need this)

## Step 5: Configure Your Django Service
1. Click on your main service (the one that says "Deploying from GitHub")
2. Go to **"Variables"** tab
3. Add these environment variables:

### Required Variables:
```
DJANGO_SECRET_KEY=<generate-a-random-secret-key>
DEBUG=False
ALLOWED_HOSTS=*.railway.app,your-custom-domain.com
DB_NAME=<from MySQL service - MYSQLDATABASE>
DB_USER=<from MySQL service - MYSQLUSER>
DB_PASSWORD=<from MySQL service - MYSQLPASSWORD>
DB_HOST=<from MySQL service - MYSQLHOST>
DB_PORT=<from MySQL service - MYSQLPORT>
CELERY_BROKER_URL=<from Redis service - REDIS_URL>
CELERY_RESULT_BACKEND=<from Redis service - REDIS_URL>
CORS_ALLOW_ALL_ORIGINS=False
FRONTEND_URL=https://your-frontend-url.com
```

### Optional (Email Configuration):
```
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password
DEFAULT_FROM_EMAIL=noreply@ierms.denr.gov.ph
```

### Generate Secret Key:
Run this command locally to generate a secure secret key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

## Step 6: Deploy
1. Railway will automatically detect your `Procfile` and deploy
2. Wait for the build to complete (check the "Deployments" tab)
3. Your app will be live at `https://your-service-name.up.railway.app`

## Step 7: Run Migrations
1. Go to your service → **"Deployments"** tab
2. Click on the latest deployment
3. Click **"Run Command"**
4. Run: `cd server && python manage.py migrate`
5. Create superuser: `cd server && python manage.py createsuperuser`

## Step 8: Collect Static Files
1. In the same "Run Command" interface
2. Run: `cd server && python manage.py collectstatic --noinput`

## Step 9: Add Worker Processes (Optional - for Celery)
If you need Celery workers:

1. Go to your project dashboard
2. Click **"New"** → **"Empty Service"**
3. Connect it to the same GitHub repo
4. Go to **"Settings"** → **"Service Type"** → Change to **"Worker"**
5. Set **"Start Command"** to: `cd server && celery -A core worker --loglevel=info`
6. Add the same environment variables from Step 5

## Step 10: Custom Domain (Optional)
1. Go to your service → **"Settings"** tab
2. Scroll to **"Domains"**
3. Click **"Generate Domain"** or **"Custom Domain"**
4. Update `ALLOWED_HOSTS` to include your custom domain

## Troubleshooting

### Build Fails
- Check the build logs in the "Deployments" tab
- Ensure `server/requirements.txt` is correct
- Verify Python version in `runtime.txt`

### Database Connection Error
- Verify all database environment variables are set correctly
- Check that MySQL service is running
- Ensure `DB_HOST` includes the full hostname (not just IP)

### Static Files Not Loading
- Run `collectstatic` command (Step 8)
- Check that `whitenoise` is in requirements.txt (it is!)

### CORS Errors
- Set `CORS_ALLOW_ALL_ORIGINS=False`
- Add your frontend URL to `FRONTEND_URL` variable
- Or manually add it to `CORS_ALLOWED_ORIGINS` in settings.py

## Cost
- Railway offers a **$5/month** starter plan with $5 credit
- Free tier available but limited
- MySQL and Redis are included in the plan

## Next Steps
1. Set up monitoring
2. Configure backups
3. Set up CI/CD (already done with GitHub integration!)
4. Add custom domain
5. Configure email service

Your Django app is now live! 🎉

