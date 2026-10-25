# Used ONLY by Render (or any cloud host). You do NOT need Docker on your laptop.
# This image already has Chromium + all the Linux libraries Playwright needs.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt "playwright==1.63.0" psycopg2-binary \
 && python -m playwright install chromium

COPY . .
WORKDIR /app/backend

ENV HOST=0.0.0.0 \
    HEADLESS=true \
    AUDIT_WORKERS=1 \
    PYTHONUNBUFFERED=1

# Render gives the port in $PORT; config.py reads it.
CMD ["python", "run.py"]
