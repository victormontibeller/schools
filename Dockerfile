FROM python:3.13-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt


FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system schools \
    && useradd --system --gid schools --home-dir /app schools

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY . /app
COPY docker/entrypoint.sh /usr/local/bin/schools-entrypoint

RUN chmod 0755 /usr/local/bin/schools-entrypoint \
    && mkdir -p /app/media /app/staticfiles \
    && SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput \
    && chown -R schools:schools /app/media /app/staticfiles

USER schools
EXPOSE 8000

ENTRYPOINT ["schools-entrypoint"]
CMD ["opentelemetry-instrument", "gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/', timeout=3)"]
