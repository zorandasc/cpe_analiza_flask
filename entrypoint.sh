#!/bin/sh

# 1. Wait for the database to be ready
# The 'db' service is named 'db' in docker-compose, and its port is 5432 (inside container)
echo "Waiting for PostgreSQL to start..."

while ! nc -z db 5432; do
    sleep 0.5
done
echo "PostgreSQL started."

# --2. INITIALIZE DATABASE SCHEMA ---
# 'flask' is the main executable, 'init-db' is your custom command.
echo "Running database initialization (creating tables)..."
flask init-db

# --3. CREATE ADMIN USER----------
# 'flask' is the main executable, 'create-admin' is your custom command.
echo "Running create-admin command..."
flask create-admin

echo "Running create-report command..."
flask create-report

# --4. START THE APLICATION---
echo "Starting Flask server..."

# Use the production-ready server (e.g., gunicorn) instead of 'flask run'
#It ensures:

#exec gunicorn
#Gunicorn becomes PID 1
#Docker can stop container cleanly
#no zombie processes
#proper signal handling
exec gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 3 \
  --threads 2 \
  --timeout 120 \
  --keep-alive 5 \
  run:app