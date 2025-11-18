# ---- Builder Stage ----
FROM python:3.10-slim as builder

WORKDIR /app

RUN pip install poetry

COPY pyproject.toml poetry.lock* /app/

# Install dependencies for production
RUN poetry config virtualenvs.in-project true && \
    poetry install --no-interaction --no-ansi --without dev

# ---- Final Stage ----
FROM python:3.10-slim

WORKDIR /app

# Create a non-root user
RUN addgroup --system app && adduser --system --group app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /.venv

# Copy application code
COPY . /app/

# Set environment variables for the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

USER app

EXPOSE 8000

# Use gunicorn for production
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "--bind", "0.0.0.0:8000"]
