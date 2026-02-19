FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/cloudflare/worker/src

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y libatomic1 \
    && rm -rf /var/lib/apt/lists/*

COPY api/pyproject.toml ./pyproject.toml
COPY api/src ./src
COPY api/tests ./tests
COPY api/scripts ./scripts
COPY cloudflare/worker/src/for_us_shared ./cloudflare/worker/src/for_us_shared
COPY extension/userscript ./extension/userscript
COPY brand/icons/web ./brand/icons/web

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[dev]" \
    && chmod +x ./scripts/*.sh

EXPOSE 8000

CMD ["./scripts/run-api.sh"]
