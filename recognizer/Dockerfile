FROM python:3.11-slim

# Install system dependencies for EasyOCR, pdf2image, and document processing
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # For pdf2image (PDF to image conversion)
    poppler-utils \
    # For lxml (HTML parsing)
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set EasyOCR model cache directory
ENV EASYOCR_MODULE_PATH=/root/.EasyOCR

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download EasyOCR models for Russian and English
# Models will be cached in /root/.EasyOCR (mounted as volume in production)
RUN python -c "import easyocr; easyocr.Reader(['ru', 'en'], gpu=False, download_enabled=True)"

# Copy application code
COPY . .

# Startup script that ensures models are ready
COPY <<EOF /app/entrypoint.sh
#!/bin/bash
set -e

echo "=== DocRAG Recognizer Service ==="
echo "Checking EasyOCR models..."

# Ensure models are available (will use cached if present, download if not)
python -c "
import easyocr
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('startup')

logger.info('Loading EasyOCR models (ru, en)...')
reader = easyocr.Reader(['ru', 'en'], gpu=False, download_enabled=True)
logger.info('EasyOCR models ready!')
"

echo "Starting Recognizer worker..."
exec python main.py
EOF

RUN chmod +x /app/entrypoint.sh

# Run the worker via entrypoint
CMD ["/app/entrypoint.sh"]
