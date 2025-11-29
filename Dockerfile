# Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create a non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

# Create logs directory and set ownership
RUN mkdir -p /app/logs && chown appuser:appuser /app/logs

# Install poetry
RUN pip install poetry

# Copy only the files necessary for dependency installation to leverage Docker cache
COPY pyproject.toml poetry.lock* /app/

# Install dependencies (Production only)
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root



# Copy the rest of the application code
COPY . /app/

# Change ownership of the application code to the non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Command to run the application
CMD bash -c "python /app/scripts/wait-for-db.py && poetry run alembic upgrade head && poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000"
