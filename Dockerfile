FROM python:3.11-slim

# Install Node.js 20 (compatible with Vite)
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY server/requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Copy and install Node.js dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy application code
COPY . .

# Build frontend
RUN npm run build

# Collect static files - FIXED: No cd command
RUN python server/manage.py collectstatic --noinput

# Set final working directory
WORKDIR /app/server

# FIXED: Simple CMD without cd
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2", "--timeout", "120"]