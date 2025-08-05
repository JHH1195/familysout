FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    build-essential \
    poppler-utils \
    && apt-get clean

COPY python_app/ .  # Pfad anpassen, da dieser Dockerfile im Root liegt

RUN pip install --no-cache-dir -r requirements.txt

CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]
