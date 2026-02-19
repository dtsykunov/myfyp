FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y libatomic1 \
    && rm -rf /var/lib/apt/lists/*

COPY cloudflare/worker/pyproject.toml ./cloudflare/worker/pyproject.toml
COPY cloudflare/worker/src ./cloudflare/worker/src
COPY cloudflare/worker/tests ./cloudflare/worker/tests
COPY cloudflare/worker/scripts ./cloudflare/worker/scripts
COPY cloudflare/worker/pyrightconfig.json ./cloudflare/worker/pyrightconfig.json
COPY cloudflare/worker/wrangler.toml ./cloudflare/worker/wrangler.toml
COPY cloudflare/worker/migrations ./cloudflare/worker/migrations

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e "./cloudflare/worker[dev]" \
    && pip install --no-cache-dir workers-py \
    && chmod +x ./cloudflare/worker/scripts/*.sh

ENV PYTHONPATH=/app/cloudflare/worker/src

CMD ["./cloudflare/worker/scripts/run-tests.sh"]
