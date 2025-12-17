FROM python:3.11-slim

# Install system dependencies for EasyOCR
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download EasyOCR models for Russian and English
RUN python -c "import easyocr; easyocr.Reader(['ru', 'en'], gpu=False)"

# Copy application code
COPY . .

# Run the worker
CMD ["python", "main.py"]
