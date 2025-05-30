FROM python:3.9-slim

WORKDIR /app

# install additional system dependencies
RUN apt-get update && apt-get install -y \
    curl && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK resources during build
RUN python -m nltk.downloader punkt
RUN python -m nltk.downloader punkt_tab

# Download spaCy model during build
RUN python -m spacy download de_core_news_md

# Copy application files, excluding the requirements file
COPY . .
RUN rm -f /app/requirements.txt

# Create entrypoint script
RUN echo '#!/bin/bash' > /app/entrypoint.sh && \
    echo '# Default to today if no date specified' >> /app/entrypoint.sh && \
    echo 'if [ $# -eq 0 ]; then' >> /app/entrypoint.sh && \
    echo '  echo "Running: python run.py --date latest"' >> /app/entrypoint.sh && \
    echo '  python run.py --date latest' >> /app/entrypoint.sh && \
    echo 'else' >> /app/entrypoint.sh && \
    echo '  # Pass all arguments directly to the Python script' >> /app/entrypoint.sh && \
    echo '  echo "Running: python run.py $@"' >> /app/entrypoint.sh && \
    echo '  python run.py "$@"' >> /app/entrypoint.sh && \
    echo 'fi' >> /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
