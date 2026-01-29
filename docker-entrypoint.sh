#!/bin/bash
set -e

# Применяем миграции
echo "Applying database migrations..."
alembic upgrade head

# Запускаем приложение
echo "Starting application..."
exec "$@"
