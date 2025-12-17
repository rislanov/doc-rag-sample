FROM python:3.11-slim

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Startup script that ensures Ollama embedding model is ready
COPY <<EOF /app/entrypoint.sh
#!/bin/bash
set -e

echo "=== DocRAG Semantic Chunker Service ==="

# Wait for Ollama to be available and embedding model to be loaded
OLLAMA_URL=\${OLLAMA_BASE_URL:-http://localhost:11434}
EMBEDDING_MODEL=\${EMBEDDING_MODEL:-evilfreelancer/enbeddrus}

echo "Waiting for Ollama at \$OLLAMA_URL..."

# Wait for Ollama API
until curl -sf "\$OLLAMA_URL/api/tags" > /dev/null 2>&1; do
    echo "Ollama not ready, waiting..."
    sleep 5
done

echo "Ollama is ready. Checking embedding model \$EMBEDDING_MODEL..."

# Check if model is available, if not wait for it
python -c "
import requests
import time
import os

ollama_url = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
model = os.environ.get('EMBEDDING_MODEL', 'evilfreelancer/enbeddrus')

print(f'Verifying embedding model {model} is ready...')

# Try to generate a test embedding
max_retries = 30
for i in range(max_retries):
    try:
        resp = requests.post(
            f'{ollama_url}/api/embeddings',
            json={'model': model, 'prompt': 'test'},
            timeout=60
        )
        if resp.status_code == 200:
            data = resp.json()
            if 'embedding' in data and len(data['embedding']) > 0:
                print(f'Embedding model ready! Dimension: {len(data[\"embedding\"])}')
                break
    except Exception as e:
        print(f'Attempt {i+1}/{max_retries}: Model not ready ({e})')
    time.sleep(10)
else:
    print('WARNING: Could not verify embedding model, continuing anyway...')
"

echo "Starting Semantic Chunker worker..."
exec python main.py
EOF

RUN chmod +x /app/entrypoint.sh

# Run the worker via entrypoint
CMD ["/app/entrypoint.sh"]
