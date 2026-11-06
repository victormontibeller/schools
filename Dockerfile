FROM python:3.13-slim@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962 AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN pip install --require-hashes -r /tmp/requirements.lock \
    && /opt/venv/bin/python -m pip uninstall --yes pip


FROM python:3.13-slim@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962 AS runtime

ENV OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=django,logging \
    OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=false \
    OTEL_LOGS_EXPORTER=none \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

ARG APP_UID=10001
ARG APP_GID=10001

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid "${APP_GID}" schools \
    && useradd --system --uid "${APP_UID}" --gid schools --home-dir /app schools

RUN /usr/local/bin/python -m pip uninstall --yes pip

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
CMD ["opentelemetry-instrument", "gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-", "--access-logformat", "status=%(s)s duration=%(L)s bytes=%(b)s"]
