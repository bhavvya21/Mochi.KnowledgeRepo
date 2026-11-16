FROM node:24-bookworm-slim AS frontend
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY index.html ./
COPY src ./src
RUN npx vite build --outDir build-client

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend MODEL_CACHE=/opt/mochi-models
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend ./backend
RUN python -c "from mochi.models import LocalModels; from mochi.config import Settings; LocalModels(Settings()).load()"
COPY benchmarks ./benchmarks
COPY --from=frontend /app/build-client ./build-client
RUN useradd --create-home mochi && chown -R mochi:mochi /app /opt/mochi-models
USER mochi
EXPOSE 8000
CMD ["sh", "-c", "uvicorn mochi.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
