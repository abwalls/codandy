FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CODANDY_ENVIRONMENT=production \
    CODANDY_WORKSPACE_ROOT=/tmp/codandy-workspaces

RUN apt-get update \
    && apt-get install --no-install-recommends -y git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --system
COPY app ./app

RUN useradd --create-home --uid 10001 atlas \
    && mkdir -p /tmp/codandy-workspaces \
    && chown -R atlas:atlas /app /tmp/codandy-workspaces
USER atlas

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
