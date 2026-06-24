#!/bin/bash
set -e

echo "Initializing database..."
python /app/init_db.py

echo "Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 --workers 4 app:app
