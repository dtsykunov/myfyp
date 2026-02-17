FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./pyproject.toml
COPY src ./src
COPY tests ./tests
COPY scripts ./scripts

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[dev]" \
    && chmod +x ./scripts/*.sh

EXPOSE 8000

CMD ["./scripts/run-api.sh"]
