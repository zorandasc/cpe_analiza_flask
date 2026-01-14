# ============================
# 1) Base image for building
# ============================
FROM python:3.12-slim AS builder

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
# Prevent buffering (better logs)
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install build dependencies (PostgreSQL client & headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install dependencies to /install folder
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============================
# 2) Final runtime image
# ============================
FROM python:3.12-slim

WORKDIR /app

# 1. Install necessary system utilities in the FINAL image (netcat for entrypoint.sh)
# Since you build locally WITH internet, this works.
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    # libpq5 is the PostgreSQL client library needed at runtime
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# 2. Add the entrypoint scrip
COPY entrypoint.sh /usr/local/bin/
# make the script exsecutable
RUN chmod +x /usr/local/bin/entrypoint.sh

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy project files
COPY . .

# Default port Flask/Gunicorn will listen on
EXPOSE 5000
# Environment variable for Flask
ENV FLASK_APP=run.py

# Set the Entrypoint to run your script first
# specifies the program that runs when a container starts.
ENTRYPOINT ["entrypoint.sh"]

# Set the default command (will be run by exec in the entrypoint script)
# Command for production (Gunicorn)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]