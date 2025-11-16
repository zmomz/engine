# Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install poetry
RUN pip install poetry
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

# Copy only the files necessary for dependency installation to leverage Docker cache
COPY pyproject.toml poetry.lock* /app/

# Copy the rest of the application code
COPY . /app/

# Update the lock file and install dependencies
RUN poetry lock
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi --with dev

# Command to run the application
CMD ["bash"]
