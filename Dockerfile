FROM python:3.11-slim

# Install Node.js (use a compatible version)
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    xz-utils \
    && curl -fsSL https://nodejs.org/dist/v20.18.0/node-v20.18.0-linux-x64.tar.xz -o node.tar.xz \
    && tar -xJf node.tar.xz -C /usr/local --strip-components=1 \
    && rm node.tar.xz \
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

# Collect static files - FIXED: Use absolute path instead of cd
RUN python server/manage.py collectstatic --noinput

# Set final working directory
WORKDIR /app/server

# Use shell form for CMD to handle environment variables
CMD gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 120