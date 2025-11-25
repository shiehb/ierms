FROM python:3.11-slim

# Install Node.js
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

# Copy and setup start script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

WORKDIR /app/server

# Use the start script
CMD ["/app/start.sh"]