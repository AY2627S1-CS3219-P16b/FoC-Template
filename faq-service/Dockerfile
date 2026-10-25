FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    FAQ_MODEL_CACHE=/opt/faq-models FAQ_MODEL_LOCAL_ONLY=true \
    HF_HUB_DISABLE_TELEMETRY=1 TOKENIZERS_PARALLELISM=false
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Download the local ONNX model at build time. Startup and requests need no
# Hugging Face access and never download or reload model weights per question.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/opt/faq-models', threads=2)"
COPY app ./app
COPY docs ./docs
COPY evaluation ./evaluation
RUN useradd --uid 10001 --create-home faq && chmod -R a+rX /opt/faq-models
USER faq
EXPOSE 8004
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=12 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8004/health', timeout=3)"]
CMD ["sh", "-c", "python -m app.ingest && exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8004"]
