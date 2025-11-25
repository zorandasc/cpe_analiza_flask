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

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy project files
COPY . .

# Default port Flask/Gunicorn will listen on
EXPOSE 5000

# Environment variable for Flask
ENV FLASK_APP=app.py

# Command for production (Gunicorn)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]