FROM node:20-alpine as frontend

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY server/requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Copy built frontend from the first stage
COPY --from=frontend /app/dist /app/dist
COPY server /app/server

# Collect static files
WORKDIR /app/server
RUN python manage.py collectstatic --noinput

CMD gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 120