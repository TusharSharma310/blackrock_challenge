# Build command: docker build -t blk-hacking-ind-name-lastname .
# Run command: docker run -d -p 5477:5477 blk-hacking-ind-name-lastname

# Using Python 3.11-slim based on Debian Linux (Bullseye).
# Selection criteria:
#   - Python 3.11: Latest stable Python with improved performance (~10-60% faster than 3.10)
#   - Slim variant: Minimal attack surface, smaller image (~70% smaller than full image)
#   - Debian-based: Better compatibility with binary Python packages (psutil, uvicorn)
#   - Official Python image: Regularly patched, trusted supply chain
FROM python:3.11-slim

# Set environment variables for production
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PORT=5477 \
    WORKERS=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user for security
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

# Set working directory
WORKDIR /app

# Install system dependencies (minimal set)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (Docker layer caching optimization)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app/ ./app/

# Change ownership to non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose port 5477 as per challenge requirements
EXPOSE 5477

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5477/health')" || exit 1

# Run the application
# Using uvicorn directly for production with proper settings
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "5477", \
     "--workers", "1", \
     "--log-level", "info", \
     "--access-log", \
     "--no-use-colors"]
