FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set cache directory for HuggingFace models
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the model during build (makes container start faster)
# This downloads ~560MB model weights
RUN python -c "
from sentence_transformers import CrossEncoder
print('Downloading BAAI/bge-reranker-v2-m3...')
model = CrossEncoder('BAAI/bge-reranker-v2-m3', max_length=512)
# Warmup
_ = model.predict([('test', 'test')])
print('Model downloaded and ready!')
"

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
