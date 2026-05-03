# --- stage 1: build the Vue frontend ---
FROM node:22-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- stage 2: python runtime ---
FROM python:3.13-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    ADDTOVIEW_SERVE_STATIC=1 \
    ADDTOVIEW_STATIC_DIR=/app/frontend/dist \
    DATA_DIR=/app/data \
    ADDTOVIEW_PORTS=2232,2233 \
    ADDTOVIEW_IN_CONTAINER=1

WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/ ./
COPY --from=frontend-build /build/dist /app/frontend/dist

EXPOSE 2232 2233
CMD ["python", "serve.py"]
