# Use Python 3.13 slim image as base
FROM python:3.13-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_VERSION=0.1.13

# Install system dependencies and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-linux-amd64.tar.gz | \
    tar zxf - -C /usr/local/bin

# Create and set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY atria ./atria
COPY emporio ./emporio
COPY plethora ./plethora
COPY shipping ./shipping
COPY socialize ./socialize
COPY manage.py ./

# Install production dependencies only
RUN uv pip install --system -e ".[prod]"

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
