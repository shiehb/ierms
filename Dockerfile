FROM python:3.11-slim

# Install Node.js 20
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js dependencies and build
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Collect static files
RUN python server/manage.py collectstatic --noinput

# Final working directory
WORKDIR /app/server

# Simple CMD without any cd commands
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2", "--timeout", "120"]