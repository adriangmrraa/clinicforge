FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY orchestrator_service/requirements.txt .

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi-dev shared-mime-info fonts-liberation fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

COPY orchestrator_service/ .
COPY shared/ ./shared/

RUN chmod +x start.sh

CMD ["./start.sh"]
