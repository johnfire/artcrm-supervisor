FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy all agent packages and supervisor
COPY artcrm-research-agent/    ./artcrm-research-agent/
COPY artcrm-enrichment-agent/  ./artcrm-enrichment-agent/
COPY artcrm-scout-agent/       ./artcrm-scout-agent/
COPY artcrm-outreach-agent/    ./artcrm-outreach-agent/
COPY artcrm-followup-agent/    ./artcrm-followup-agent/
COPY artcrm-interview-agent/   ./artcrm-interview-agent/
COPY artcrm-supervisor/        ./artcrm-supervisor/

WORKDIR /app/artcrm-supervisor

# Install all deps including agents (editable installs resolved locally)
RUN uv sync --extra agents --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
