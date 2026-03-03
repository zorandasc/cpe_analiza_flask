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

#exec replaces the current shell process with the Gunicorn process, 
# which is commonly used in startup scripts to ensure the application 
# runs as PID 1 and receives system signals directly.
#Gunicorn becomes PID 1
#Docker can stop container cleanly, no zombie processes and proper signal handling
# enables threading with 2 threads per worker
#--timeout 120 sets the maximum time (in seconds) a worker can take to process a request 
#--keep-alive 5 enables HTTP keep-alive with a 5-second timeout, allowing reuse of connections for multiple requests.
exec gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 3 \
  --threads 2 \
  --timeout 120 \
  --keep-alive 5 \
  run:app