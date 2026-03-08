# Stage 1: Build dashboard frontend
FROM node:20-slim AS dashboard-builder
WORKDIR /app/dashboard
COPY server/dashboard/package*.json ./
RUN npm ci
COPY server/dashboard/ ./
RUN npm run build

# Stage 2: Python MCP server + engine content + dashboard static files
FROM python:3.12-slim AS app

WORKDIR /app

# System deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy engine content
COPY ENGINE_VERSION.yaml CLAUDE.md install.sh ./
COPY .claude/ .claude/
COPY architecture/ architecture/
COPY infra/ infra/
COPY design/ design/
COPY agents/ agents/
COPY agent-teams/ agent-teams/
COPY templates/ templates/
COPY rules/ rules/
COPY commands/ commands/
COPY doc/ doc/
COPY docs/ docs/
COPY .quality/ .quality/

# Copy server code
COPY server/ server/

# Copy dashboard build from frontend stage
COPY --from=dashboard-builder /app/dashboard/dist server/dashboard/dist

ENV PYTHONUNBUFFERED=1
ENV ENGINE_PATH=/app
ENV STATE_PATH=/data/state
ENV MCP_TRANSPORT=http
ENV MCP_PORT=8000

VOLUME /data/state

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "server"]
