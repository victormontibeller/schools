#!/bin/sh
set -eu

load_secret() {
    variable="$1"
    file_variable="${variable}_FILE"
    eval "file_path=\${$file_variable:-}"
    if [ -n "${file_path}" ] && [ -r "${file_path}" ]; then
        value=$(tr -d '\r\n' < "${file_path}")
        export "${variable}=${value}"
    fi
}

for variable in SECRET_KEY DB_PASSWORD REDIS_PASSWORD RABBITMQ_PASSWORD METRICS_TOKEN READINESS_TOKEN; do
    load_secret "${variable}"
done

if [ -n "${REDIS_PASSWORD:-}" ] && [ -z "${REDIS_URL:-}" ]; then
    export REDIS_URL="redis://:${REDIS_PASSWORD}@redis:6379/0"
fi
if [ -n "${RABBITMQ_PASSWORD:-}" ] && [ -z "${RABBITMQ_URL:-}" ]; then
    export RABBITMQ_URL="amqp://schools:${RABBITMQ_PASSWORD}@rabbitmq:5672//"
fi

exec "$@"
