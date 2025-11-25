FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    xz-utils \
    && curl -fsSL https://nodejs.org/dist/v18.20.4/node-v18.20.4-linux-x64.tar.xz -o node.tar.xz \
    && tar -xJf node.tar.xz -C /usr/local --strip-components=1 \
    && rm node.tar.xz \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY server/requirements.txt /app/server/requirements.txt

RUN pip install --upgrade pip setuptools wheel && \
    pip install -r server/requirements.txt

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

RUN npm run build

RUN cd server && python manage.py collectstatic --noinput || true

ENV PORT=8000
EXPOSE 8000

# Fix: enter backend folder before running Gunicorn
WORKDIR /app/server
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:${PORT}", "--workers", "2", "--threads", "2", "--timeout", "120"]
