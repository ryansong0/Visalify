FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-backend.txt .
RUN pip install --no-cache-dir -r requirements-backend.txt
RUN python -m spacy download en_core_web_sm

COPY app ./app

# Hugging Face Spaces expects the container to listen on 7860 and runs as a
# non-root user by default; match that so file permissions behave correctly.
RUN useradd -m -u 1000 appuser
USER appuser

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
