# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set environment variables
# Prevents Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE=1 \
    # Prevents Python from buffering stdout and stderr
    PYTHONUNBUFFERED=1 \
    # Poetry environment variables
    POETRY_VERSION=1.8.0 \
    POETRY_HOME="/opt/poetry" \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    # Add poetry to PATH
    PATH="/opt/poetry/bin:$PATH"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    chmod +x /opt/poetry/bin/poetry

# Copy Poetry configuration files
COPY pyproject.toml poetry.lock ./

# Install Python dependencies using Poetry
# --no-root: Don't install the project itself, just dependencies
# --only main: Only install main dependencies (not dev dependencies)
RUN poetry install --no-root --only main

# Copy application code
COPY app.py .
COPY translations.yaml .

# Copy configuration file if it exists, otherwise use template
# The actual config should be mounted as a volume in production
COPY .appconfig.yaml* ./
RUN if [ ! -f .appconfig.yaml ]; then \
    if [ -f .appconfig.template.yaml ]; then \
        cp .appconfig.template.yaml .appconfig.yaml; \
    fi; \
    fi

# Create data directory for database storage
RUN mkdir -p /app/data

# Expose Streamlit's default port
EXPOSE 8501

# Health check to ensure the app is running
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run the Streamlit application
CMD ["poetry", "run", "streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
