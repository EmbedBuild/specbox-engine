FROM python:3.12-slim AS app

WORKDIR /app

# System deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Cache-bust: bump this ARG (or pass --build-arg CACHEBUST=$(date)) to force a
# fresh recopy of all engine content + server code below. Needed because some
# CI/PaaS builders (e.g. EasyPanel) reuse a stale :latest image and skip the
# COPY cache-key re-evaluation, leaving an old engine version baked in.
ARG CACHEBUST=2026-05-25-v6.1.0

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
COPY doc/ doc/
COPY docs/ docs/
COPY .quality/ .quality/

# Copy server code
COPY server/ server/

ENV PYTHONUNBUFFERED=1
ENV ENGINE_PATH=/app
ENV STATE_PATH=/data/state
ENV MCP_TRANSPORT=http
ENV MCP_PORT=8000

VOLUME /data/state

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

CMD ["python", "-m", "server"]
