FROM python:3.11-slim-bookworm

WORKDIR /app

# Install system dependencies for PDF processing and OCR
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng && \
    rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir \
    nearai \
    openai \
    pdf2image \
    pytesseract

# Create the hardcoded data directories required by config.py
# The application's config.py uses a hardcoded path like /Users/georgemarlow/...
# This Dockerfile creates this exact path within the container.
# For production use, consider modifying config.py to use an environment variable
# for the base path, and then mount a volume to that path.
RUN mkdir -p /Users/georgemarlow/.nearai/registry/dailies.near/news-agent/0.1.5/pdfs && \
    mkdir -p /Users/georgemarlow/.nearai/registry/dailies.near/news-agent/0.1.5/dataset/newspapers && \
    mkdir -p /Users/georgemarlow/.nearai/registry/dailies.near/news-agent/0.1.5/vector

# The entry point for nearai agents is typically handled by the nearai runtime.
# This command assumes 'nearai run .' is used to execute the agent in the current directory.
CMD ["nearai", "run", "."]