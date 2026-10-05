FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# CPU-only torch, installed first so sentence-transformers finds the
# requirement already satisfied. Pip's default wheel bundles the CUDA
# runtime — nvidia/* and triton came to ~4GB of GPU libraries that a CPU
# host never loads.
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir torch==2.14.1 \
        --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Bake the embedding model into the image so no one ever waits for the
# ~90MB download at request time. Sits above `COPY . .` so code changes
# don't invalidate the layer and force a re-download.
ARG EMBEDDING_MODEL=all-MiniLM-L6-v2
ENV EMBEDDING_MODEL=${EMBEDDING_MODEL}
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('${EMBEDDING_MODEL}')"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
