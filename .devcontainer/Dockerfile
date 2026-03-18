# Use your base image for development
FROM williamlagos/eos:latest

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONBREAKPOINT=ipdb.set_trace \
    DJANGO_SETTINGS_MODULE=atria.settings \
    PATH="/home/vscode/.local/bin:${PATH}"

# Install system dependencies
RUN pacman --noconfirm -Syu \
    python \
    python-pip \
    git \
    curl \
    postgresql-libs \
    && pacman -Scc --noconfirm

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.10.10 /uv /usr/local/bin/uv

# Create non-root user
RUN useradd -m -s /bin/bash vscode \
    && mkdir -p /app \
    && chown -R vscode:vscode /app

# Switch to non-root user
USER vscode
WORKDIR /app

# We'll mount the project directory in devcontainer.json
# No need to copy files here

# Install development tools
RUN uv pip install --user \
    ipdb \
    debugpy

# The command will be overridden by devcontainer.json
CMD ["sleep", "infinity"] 
