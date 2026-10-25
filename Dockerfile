FROM node:22-alpine AS frontend
WORKDIR /webapp
COPY webapp/package.json webapp/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY webapp/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEV_BROWSER_MODE=false

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bekstyle ./bekstyle
COPY --from=frontend /webapp/dist/ ./bekstyle/static/

EXPOSE 10000
VOLUME ["/app/data"]

CMD ["python", "-m", "bekstyle"]
