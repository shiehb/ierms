FROM python:3.11-slim

# Install Node.js 20 (compatible with your Vite requirements)
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first
COPY server/requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Install Node.js dependencies and build
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

# Collect static files
WORKDIR /app/server
RUN python manage.py collectstatic --noinput

# Final CMD - use shell form
CMD gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 120