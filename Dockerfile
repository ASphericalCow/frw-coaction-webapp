# Stage 1: build the React frontend
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# Empty VITE_API_URL = use relative URLs (FastAPI serves both API and static files)
ENV VITE_API_URL=""
RUN npm run build

# Stage 2: Python backend with bundled frontend
FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend-build /app/frontend/dist ./dist

# Cloud Run injects $PORT (default 8080). Honor it; fall back to 8001 locally.
ENV PORT=8080
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
