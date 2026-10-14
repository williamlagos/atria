# Use Python 3.11 slim image as base matching local environment
FROM python:3.11-slim AS builder

# Copy uv from the official image
COPY --from=ghcr.io/astral-sh/uv:0.10.10 /uv /usr/local/bin/uv

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies including libpq-dev for PostgreSQL support
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Copy project definition and files
COPY pyproject.toml README.md ./
COPY atria ./atria
COPY manage.py ./

# Install production dependencies
RUN uv pip install --system -e "."

# Development stage
FROM builder AS dev

# Install dev dependencies
RUN uv pip install --system -e ".[dev]"

# Final production stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=atria.settings

WORKDIR /app

# Copy installed packages and project files from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app .

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r django && useradd -r -g django django \
    && chown -R django:django /app

# Collect static files with an ephemeral compilation key
RUN SECRET_KEY=build-time-asset-compilation-key python manage.py collectstatic --noinput

USER django

# Expose port
EXPOSE 8000

# Run gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "atria.wsgi"]
