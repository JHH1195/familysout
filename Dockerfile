FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-deu \
    build-essential \
    poppler-utils \
    && apt-get clean && rm -rf /var/lib/apt/lists/*


# Copy application code
COPY python_app/ /app/

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

# Start with Gunicorn in production
CMD ["bash", "-lc", "exec gunicorn -w 2 -k gthread -b 0.0.0.0:${PORT:-8080} app:app"]
