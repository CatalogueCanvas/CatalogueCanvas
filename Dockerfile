# --- Stage 1: build the React SPA ---
FROM node:22-slim AS web-build
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# --- Stage 2: Python runtime ---
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY server/pyproject.toml server/uv.lock /app/server/
COPY server/src /app/server/src
RUN cd server && uv sync --frozen --no-dev

COPY --from=web-build /app/web/dist /app/web/dist

ENV CC_DATA_DIR=/data \
    CC_STATIC_DIR=/app/web/dist \
    PATH="/app/server/.venv/bin:${PATH}"

VOLUME /data
EXPOSE 8000

WORKDIR /app/server
CMD ["uv", "run", "uvicorn", "cataloguecanvas.main:app", "--host", "0.0.0.0", "--port", "8000"]
