#!/usr/bin/env bash
set -e

# Install Python dependencies
pip install -r backend/requirements.txt

# Build React frontend with relative API URL (served by same backend in production)
cd frontend
VITE_API_URL="" npm ci
VITE_API_URL="" npm run build
cd ..

# Copy built frontend into backend/dist so FastAPI can serve it
rm -rf backend/dist
cp -r frontend/dist backend/dist
echo "Build complete: backend/dist ready"
