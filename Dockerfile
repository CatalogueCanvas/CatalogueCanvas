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

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ARG CC_GIT_SHA=unknown
ARG CC_BUILD_DATE=unknown

ENV CC_DATA_DIR=/data \
    CC_STATIC_DIR=/app/web/dist \
    CC_GIT_SHA=${CC_GIT_SHA} \
    CC_BUILD_DATE=${CC_BUILD_DATE} \
    PATH="/app/server/.venv/bin:${PATH}"

VOLUME /data
EXPOSE 8000

# Run as an unprivileged user. /data (volume) and /app must be writable by it:
# the entrypoint generates a session key under /data on first boot.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /app
USER appuser

WORKDIR /app/server
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uv", "run", "uvicorn", "cataloguecanvas.main:app", "--host", "0.0.0.0", "--port", "8000"]
