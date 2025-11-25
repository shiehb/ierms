#############################################
# 1) FRONTEND BUILD STAGE (Node 20 for Vite)
#############################################
FROM node:20-alpine AS frontend

WORKDIR /app

# Copy only the package files first to leverage caching
COPY package.json package-lock.json* ./

# Install frontend dependencies
RUN npm ci

# Copy the rest of your project (frontend part)
COPY . .

# Build Vite frontend
RUN npm run build


#############################################
# 2) BACKEND STAGE (Python 3.11 Slim)
#############################################
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# System dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend requirements
COPY server/requirements.txt /app/server/requirements.txt

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r server/requirements.txt

# Copy backend code
COPY server /app/server

# Copy built frontend from stage 1 into Django static folder
COPY --from=frontend /app/dist /app/server/staticfiles

# Collect static files
RUN cd server && python manage.py collectstatic --noinput || true

# Expose port
ENV PORT=8000
EXPOSE 8000

# Start Gunicorn
CMD cd server && gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 120
