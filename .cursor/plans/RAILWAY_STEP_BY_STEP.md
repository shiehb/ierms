# Railway Deployment - Step by Step Guide

Follow these steps in order to deploy your Django application to Railway.

---

## ✅ STEP 1: Sign Up for Railway

1. **Go to Railway**: Open your browser and visit [https://railway.app](https://railway.app)
2. **Click "Start a New Project"** or **"Login"** if you already have an account
3. **Sign up with GitHub** (recommended - easiest way):
   - Click "Login with GitHub"
   - Authorize Railway to access your GitHub account
   - This allows Railway to automatically deploy from your repository

**✅ Checkpoint**: You should now be on the Railway dashboard

---

## ✅ STEP 2: Create a New Project

1. **Click the "New Project" button** (usually a big green button or "+" icon)
2. **Select "Deploy from GitHub repo"**
3. **Authorize Railway** (if prompted) to access your GitHub repositories
4. **Search for your repository**: `integrated_establishments_regulatory_management_system`
5. **Click on your repository** to select it
6. **Click "Deploy Now"**

**✅ Checkpoint**: Railway will start detecting your project. You should see a service being created.

---

## ✅ STEP 3: Add MySQL Database

1. **In your Railway project dashboard**, click the **"New"** button (or **"+"** icon)
2. **Select "Database"**
3. **Choose "Add MySQL"**
4. Railway will automatically create a MySQL database
5. **Wait for the database to be provisioned** (usually takes 1-2 minutes)

**✅ Checkpoint**: You should see a new MySQL service in your project dashboard

---

## ✅ STEP 4: Get MySQL Connection Details

1. **Click on the MySQL service** you just created
2. **Go to the "Variables" tab** (or "Data" tab)
3. **Copy these values** - you'll need them in the next step:
   - `MYSQLDATABASE` - This is your database name
   - `MYSQLUSER` - This is your database user
   - `MYSQLPASSWORD` - This is your database password
   - `MYSQLHOST` - This is your database host (usually something like `containers-us-west-xxx.railway.app`)
   - `MYSQLPORT` - This is your database port (usually `3306`)

**💡 Tip**: Keep these values handy - write them down or copy to a text file temporarily

**✅ Checkpoint**: You have all MySQL connection details copied

---

## ✅ STEP 5: Add Redis (for Celery)

1. **In your Railway project dashboard**, click the **"New"** button again
2. **Select "Database"**
3. **Choose "Add Redis"**
4. Railway will automatically create a Redis instance
5. **Wait for Redis to be provisioned** (usually takes 1-2 minutes)

**✅ Checkpoint**: You should see a new Redis service in your project dashboard

---

## ✅ STEP 6: Get Redis Connection Details

1. **Click on the Redis service** you just created
2. **Go to the "Variables" tab**
3. **Copy the `REDIS_URL`** value - you'll need this for Celery

**💡 Tip**: The Redis URL usually looks like: `redis://default:password@host:port`

**✅ Checkpoint**: You have the Redis URL copied

---

## ✅ STEP 7: Configure Your Django Service Environment Variables

1. **Click on your main service** (the one that says "Deploying from GitHub" or shows your repo name)
2. **Go to the "Variables" tab**
3. **Click "New Variable"** for each of the following:

### Required Variables (Add these one by one):

#### A. Django Secret Key
- **Variable Name**: `DJANGO_SECRET_KEY`
- **Variable Value**: Generate a secure key using this command in your terminal:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(50))"
  ```
  Or use this online generator: https://djecrety.ir/
  Copy the generated key and paste it as the value

#### B. Debug Mode
- **Variable Name**: `DEBUG`
- **Variable Value**: `False`

#### C. Allowed Hosts
- **Variable Name**: `ALLOWED_HOSTS`
- **Variable Value**: `*.railway.app` (or your custom domain if you have one)

#### D. Database Configuration (Use values from Step 4)
- **Variable Name**: `DB_NAME`
- **Variable Value**: `<paste MYSQLDATABASE value>`

- **Variable Name**: `DB_USER`
- **Variable Value**: `<paste MYSQLUSER value>`

- **Variable Name**: `DB_PASSWORD`
- **Variable Value**: `<paste MYSQLPASSWORD value>`

- **Variable Name**: `DB_HOST`
- **Variable Value**: `<paste MYSQLHOST value>`

- **Variable Name**: `DB_PORT`
- **Variable Value**: `<paste MYSQLPORT value>` (usually `3306`)

#### E. Celery Configuration (Use Redis URL from Step 6)
- **Variable Name**: `CELERY_BROKER_URL`
- **Variable Value**: `<paste REDIS_URL value>`

- **Variable Name**: `CELERY_RESULT_BACKEND`
- **Variable Value**: `<paste REDIS_URL value>` (same as above)

#### F. CORS Configuration
- **Variable Name**: `CORS_ALLOW_ALL_ORIGINS`
- **Variable Value**: `False`

- **Variable Name**: `FRONTEND_URL`
- **Variable Value**: `https://iermsdeploy.vercel.app` (or your frontend URL)

### Optional Variables (Add if you have email configured):

#### G. Email Configuration
- **Variable Name**: `EMAIL_HOST_USER`
- **Variable Value**: `your-email@gmail.com`

- **Variable Name**: `EMAIL_HOST_PASSWORD`
- **Variable Value**: `your-gmail-app-password`

- **Variable Name**: `DEFAULT_FROM_EMAIL`
- **Variable Value**: `noreply@ierms.denr.gov.ph`

**✅ Checkpoint**: All environment variables are added to your Django service

---

## ✅ STEP 8: Wait for Initial Deployment

1. Railway will automatically start building and deploying your app
2. **Go to the "Deployments" tab** in your service
3. **Watch the build logs** - you should see:
   - Installing Python dependencies
   - Installing Node.js dependencies
   - Building your React frontend
   - Starting the server

**⏳ This may take 5-10 minutes** for the first deployment

**✅ Checkpoint**: Build completes successfully (check for any errors in logs)

---

## ✅ STEP 9: Run Database Migrations

1. **Go to your Django service** → **"Deployments" tab**
2. **Click on the latest deployment** (the one that just completed)
3. **Click the "..." menu** (three dots) or **"Run Command"** button
4. **Select "Run Command"** or open the terminal
5. **Run this command**:
   ```bash
   cd server && python manage.py migrate
   ```
6. **Wait for migrations to complete** - you should see "Applying migrations..."

**✅ Checkpoint**: Migrations completed successfully

---

## ✅ STEP 10: Create Superuser Account

1. **In the same terminal/command interface** from Step 9
2. **Run this command**:
   ```bash
   cd server && python manage.py createsuperuser
   ```
3. **Follow the prompts**:
   - Enter username (e.g., `admin`)
   - Enter email (e.g., `admin@example.com`)
   - Enter password (make it strong!)
   - Confirm password

**✅ Checkpoint**: Superuser created successfully

---

## ✅ STEP 11: Collect Static Files

1. **In the same terminal/command interface**
2. **Run this command**:
   ```bash
   cd server && python manage.py collectstatic --noinput
   ```
3. **Wait for static files to be collected**

**✅ Checkpoint**: Static files collected successfully

---

## ✅ STEP 12: Get Your Application URL

1. **Go to your Django service** → **"Settings" tab**
2. **Scroll down to "Domains"** section
3. **Click "Generate Domain"** (if not already generated)
4. **Copy the generated URL** - this is your backend API URL!
   - It will look like: `https://your-service-name.up.railway.app`

**✅ Checkpoint**: You have your backend URL

---

## ✅ STEP 13: Test Your Deployment

1. **Open your backend URL** in a browser
2. **You should see**:
   - Django REST Framework API root (if configured)
   - Or a 404/403 error (which is normal - means the server is running!)
3. **Test the admin panel**: Go to `https://your-url.railway.app/admin/`
4. **Login with your superuser credentials** from Step 10

**✅ Checkpoint**: Your Django backend is accessible!

---

## ✅ STEP 14: Update Frontend Configuration (Important!)

1. **Open your frontend code** (locally or in your frontend repository)
2. **Find the API configuration file**: `src/config/api.js`
3. **Update the base URL** to point to your Railway backend:
   ```javascript
   // Change from localhost to your Railway URL
   const API_BASE_URL = 'https://your-service-name.up.railway.app';
   ```
4. **Redeploy your frontend** (if it's on Vercel or another platform)

**✅ Checkpoint**: Frontend is configured to use your Railway backend

---

## ✅ STEP 15: (Optional) Set Up Celery Workers

If you need background tasks (Celery):

1. **In Railway dashboard**, click **"New"** → **"Empty Service"**
2. **Connect to the same GitHub repository**
3. **Go to "Settings"** → **"Service Type"** → Change to **"Worker"**
4. **Set "Start Command"** to:
   ```bash
   cd server && celery -A core worker --loglevel=info
   ```
5. **Copy all environment variables** from your main Django service to this worker service
6. **Deploy the worker**

**✅ Checkpoint**: Celery worker is running (optional)

---

## 🎉 Congratulations!

Your Django application is now deployed on Railway!

### Summary:
- ✅ Django backend is live
- ✅ MySQL database is connected
- ✅ Redis is configured
- ✅ Static files are served
- ✅ Admin panel is accessible
- ✅ Frontend can connect to backend

### Next Steps:
1. **Update CORS settings** if needed (add your frontend domain)
2. **Set up a custom domain** (optional - in Settings → Domains)
3. **Configure backups** for your database
4. **Set up monitoring** (Railway provides basic monitoring)
5. **Test all your API endpoints**

### Troubleshooting:

**If build fails:**
- Check the build logs in "Deployments" tab
- Verify all environment variables are set correctly
- Ensure `server/requirements.txt` is correct

**If database connection fails:**
- Double-check all DB_* environment variables
- Verify MySQL service is running
- Check that DB_HOST includes the full hostname

**If static files don't load:**
- Run `collectstatic` command again
- Check that whitenoise is in requirements.txt

**If CORS errors:**
- Verify `FRONTEND_URL` is set correctly
- Check `CORS_ALLOW_ALL_ORIGINS` is set to `False`
- Add your frontend URL to `CORS_ALLOWED_ORIGINS` in settings.py if needed

---

## 📞 Need Help?

If you encounter any issues:
1. Check Railway logs in the "Deployments" tab
2. Review environment variables are all set
3. Verify database and Redis services are running
4. Check Railway status page: https://status.railway.app

Good luck! 🚀

