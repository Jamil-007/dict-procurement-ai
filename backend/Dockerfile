# Backend Dockerfile for Cloud Run
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# tesseract-ocr backs the OCR fallback in store/files.py, for PDFs that have
# no embedded text layer (scans, print-to-PDF exports).
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p uploads

# Expose port (Cloud Run will inject PORT env var)
ENV PORT=8080
EXPOSE 8080

# Run the application
CMD exec uvicorn server:app --host 0.0.0.0 --port ${PORT} --workers 1
