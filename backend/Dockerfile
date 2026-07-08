# ReachBot backend — FastAPI RAG service.
# Build from the REPO ROOT so the 100MB index.npz (repo root) is in context:
#     docker build -f backend/Dockerfile -t reachbot-backend .
# (fly.toml sets this via [build] dockerfile + the repo-root context.)
FROM python:3.12-slim

WORKDIR /app

# Deps first for layer caching.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY backend/*.py ./

# The index. Baked into the image; the weekly job rebuilds it and redeploys.
# If the index outgrows GitHub's 100MB limit and moves to object storage, drop
# this COPY and have the app pull it at boot instead (set INDEX_PATH).
COPY index.npz ./index.npz

# Drop privileges: run as a non-root user (defense-in-depth — a compromised
# dependency shouldn't get root inside the container). /app is read-only to it,
# which is fine since the app only reads the index and never writes to disk.
RUN useradd --create-home --uid 10001 appuser
USER appuser

ENV INDEX_PATH=/app/index.npz \
    PORT=8080

EXPOSE 8080

# Single worker: the 100MB index loads once per process; more workers = more RAM.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
