FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py .

# Copy the custom wikipedia-histories plugin and install it in editable mode
COPY wikipedia-histories /app/wikipedia-histories
RUN pip install --no-cache-dir -e /app/wikipedia-histories

# Create a wrapper script to run the application and then remove the container
RUN echo '#!/bin/sh\npython run_based_summary.py "$@"\nexit_code=$?\n[ "$exit_code" -ne 0 ] && echo "Error: Application exited with code $exit_code"\nexit $exit_code' > /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
