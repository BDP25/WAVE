FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files, excluding the requirements file
COPY . .
RUN rm -f /app/requirements.txt

# Create a more flexible entrypoint script
RUN echo '#!/bin/bash\n\
# Default to today if no date specified\n\
if [ $# -eq 0 ]; then\n\
  python run.py --date today\n\
else\n\
  # Pass all arguments directly to the Python script\n\
  python run.py "$@"\n\
fi\n' > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
