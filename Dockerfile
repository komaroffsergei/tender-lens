FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app

COPY requirements.lock ./
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.lock

COPY pyproject.toml LICENSE README.md ./
COPY src ./src
COPY migrations ./migrations
COPY examples ./examples
COPY scripts ./scripts
COPY alembic.ini ./
RUN python -m pip install --no-deps . && mkdir -p /data/attachments && chown -R app:app /app /data

USER app

EXPOSE 8000
CMD ["uvicorn", "tender_lens.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
