FROM python:3.11-slim

# Install Node.js
RUN apt-get update && apt-get install -y \
    curl ca-certificates xz-utils && \
    curl -fsSL https://nodejs.org/dist/v18.20.4/node-v18.20.4-linux-x64.tar.xz -o node.tar.xz && \
    tar -xJf node.tar.xz -C /usr/local --strip-components=1 && \
    rm node.tar.xz && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY server/requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Install Node.js dependencies and build
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

# Collect static files
RUN cd server && python manage.py collectstatic --noinput

WORKDIR /app/server

# Use shell form to access PORT environment variable
CMD gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 120