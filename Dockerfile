# Use Python 3.13 slim image as base
FROM python:3.13-slim AS builder

# Copy uv from the official image
COPY --from=ghcr.io/astral-sh/uv:0.10.10 /uv /usr/local/bin/uv

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY atria ./atria
COPY shipping ./shipping
COPY socialize ./socialize
COPY manage.py ./

# Install production dependencies only
RUN uv pip install --system -e ".[prod]"

# Development stage - uses local submodule sources for live development
FROM builder AS dev

ENV PROJECT_ROOT=/app

# Install dev dependencies (uses local file:// references to submodules)
RUN uv pip install --system -e ".[dev]"

# Final stage
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=atria.settings

WORKDIR /app

# Copy installed packages and project files from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /app .

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r django && useradd -r -g django django \
    && chown -R django:django /app

# Collect static files
RUN python manage.py collectstatic --noinput

USER django

# Expose port (for documentation, not actually published)
EXPOSE 8000

# Use environment variable for port binding
CMD ["gunicorn", "--bind", "0.0.0.0:${PORT:-8000}", "atria.wsgi"]
