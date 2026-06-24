#!/bin/bash
set -e

# Wait for database to be ready
echo "Waiting for database..."
for i in {1..30}; do
  if python -c "from sqlalchemy import create_engine; create_engine('$DATABASE_URL').execute('SELECT 1')" 2>/dev/null; then
    break
  fi
  echo "Database not ready, waiting... ($i/30)"
  sleep 2
done

echo "Database is ready. Initializing schema..."
python -c "from app import init_db; init_db()"
echo "Database initialized. Starting application..."

exec "$@"
