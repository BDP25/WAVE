FROM python:3.9-slim
WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN apt-get update && apt-get install -y gcc libffi-dev python3-dev && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
RUN rm ./requirements.txt

COPY *.py .
COPY static ./static
COPY templates ./templates

EXPOSE 5050
VOLUME /data

CMD set -e; \
    mkdir -p /data/env; \
    if [ ! -f /data/env/.env ] && [ -f /default_env ]; then \
        cp /default_env /data/env/.env; \
    fi; \
    echo "Starting orchestrator with environment:"; \
    cat /data/env/.env || echo "No /data/env/.env found"; \
    exec python app.py
