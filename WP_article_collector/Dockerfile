FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py .
COPY .env* ./ 2>/dev/null || :

# Set environment variables - these will be overridden by .env file or runtime environment
ENV DB_NAME=wikipedia
ENV DB_USER=postgres
ENV DB_PASSWORD=postgres
ENV DB_HOST=host.docker.internal
ENV DB_PORT=5432

# Create a wrapper script to run the application and then remove the container
RUN echo '#!/bin/sh\npython run.py "$@"\nexit_code=$?\n[ "$exit_code" -ne 0 ] && echo "Error: Application exited with code $exit_code"\nexit $exit_code' > /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
